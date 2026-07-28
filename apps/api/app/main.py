from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from packages.contracts.poc.source import ApiError, HealthResponse, HealthStatus

from .config import Settings
from .auth import AuthenticatedUser, JwtVerifier, current_user
from .security import RateLimitMiddleware, SecurityHeadersMiddleware
from .membership import MembershipRepository
from .devices import DeviceEnrollmentRequest, DeviceRepository, EnrollmentTokenRequest, device_credential
from .enrollment import EnrollmentError, Heartbeat

settings = Settings.from_environment()
settings.validate_for_production()
app = FastAPI(
    title="YorGuard API",
    version=settings.service_version,
    docs_url="/docs" if settings.app_env != "production" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, trusted_proxy_hops=settings.trusted_proxy_hops)
app.state.jwt_verifier = JwtVerifier(
    settings.supabase_jwt_secret,
    settings.supabase_jwt_issuer,
    settings.supabase_jwt_audience,
    settings.supabase_jwt_jwks_url,
)
app.state.membership_repository = (
    MembershipRepository(settings.database_url) if settings.database_url else None
)
app.state.device_repository = DeviceRepository(settings.database_url) if settings.database_url else None


def health_response(request_id: UUID | None = None) -> HealthResponse:
    return HealthResponse(
        status=HealthStatus.healthy,
        service="yorguard-api",
        version=settings.service_version,
        checked_at=datetime.now(UTC),
        request_id=request_id or uuid4(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = uuid4()
    # Do not expose exception details or secrets in the transport response.
    return JSONResponse(
        status_code=500,
        content=ApiError(
            code="internal_error",
            message="An internal error occurred.",
            request_id=request_id,
        ).model_dump(mode="json"),
        headers={"X-Request-ID": str(request_id)},
    )


@app.get("/health/live", response_model=HealthResponse, tags=["health"])
@app.get("/api/v1/health/live", response_model=HealthResponse, tags=["health"])
async def live() -> HealthResponse:
    return health_response()


@app.get("/health/ready", response_model=HealthResponse, tags=["health"])
@app.get("/api/v1/health/ready", response_model=HealthResponse, tags=["health"])
async def ready() -> HealthResponse:
    response = health_response()
    if settings.database_url:
        try:
            import psycopg

            with psycopg.connect(settings.database_url, connect_timeout=3) as connection:
                connection.execute("select 1")
        except Exception:
            # Keep provider and connection details out of the response and logs.
            response.status = HealthStatus.degraded
            response.detail = "database unavailable"
            return JSONResponse(status_code=503, content=response.model_dump(mode="json"))
    else:
        response.detail = "database check skipped in development"
    return response


@app.get("/api/v1/auth/me", response_model=AuthenticatedUser, tags=["auth"])
async def me(user: Annotated[AuthenticatedUser, Depends(current_user)]) -> AuthenticatedUser:
    return user


def device_repository(request: Request) -> DeviceRepository:
    repository = request.app.state.device_repository
    if repository is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    return repository


def map_enrollment_error(error: EnrollmentError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error.code)


@app.get("/api/v1/devices", response_model=list, tags=["devices"])
async def devices(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[DeviceRepository, Depends(device_repository)],
) -> list:
    if user.organization_id is None:
        raise HTTPException(status_code=403, detail="Organization membership required")
    return repository.list_devices(user.organization_id)


@app.post("/api/v1/enrollment-tokens", tags=["devices"])
async def issue_enrollment_token(
    payload: EnrollmentTokenRequest,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[DeviceRepository, Depends(device_repository)],
) -> dict[str, object]:
    if user.organization_id is None or user.role not in {"owner", "administrator"}:
        raise HTTPException(status_code=403, detail="Owner or administrator role required")
    token, expires_at = repository.issue_token(user.organization_id, user.user_id, payload)
    return {"token": token, "expires_at": expires_at}


@app.post("/api/v1/devices/enroll", tags=["devices"])
async def enroll_device(
    payload: DeviceEnrollmentRequest,
    repository: Annotated[DeviceRepository, Depends(device_repository)],
) -> object:
    try:
        return repository.enroll(payload)
    except EnrollmentError as error:
        raise map_enrollment_error(error) from error


@app.post("/api/v1/devices/heartbeat", tags=["devices"])
async def device_heartbeat(
    payload: Heartbeat,
    authorization: Annotated[str, Header(alias="Authorization")],
    repository: Annotated[DeviceRepository, Depends(device_repository)],
) -> object:
    try:
        return repository.heartbeat(device_credential(authorization), payload)
    except EnrollmentError as error:
        raise map_enrollment_error(error) from error
