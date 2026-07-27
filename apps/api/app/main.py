from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from packages.contracts.poc.source import ApiError, HealthResponse, HealthStatus

from .config import Settings
from .auth import AuthenticatedUser, JwtVerifier, current_user
from .security import RateLimitMiddleware, SecurityHeadersMiddleware
from .membership import MembershipRepository

settings = Settings.from_environment()
settings.validate_for_production()
app = FastAPI(
    title="GSWGuard API",
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
app.add_middleware(RateLimitMiddleware)
app.state.jwt_verifier = JwtVerifier(
    settings.supabase_jwt_secret,
    settings.supabase_jwt_issuer,
    settings.supabase_jwt_audience,
    settings.supabase_jwt_jwks_url,
)
app.state.membership_repository = (
    MembershipRepository(settings.database_url) if settings.database_url else None
)


def health_response(request_id: UUID | None = None) -> HealthResponse:
    return HealthResponse(
        status=HealthStatus.healthy,
        service="gswguard-api",
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
    return health_response()


@app.get("/api/v1/auth/me", response_model=AuthenticatedUser, tags=["auth"])
async def me(user: Annotated[AuthenticatedUser, Depends(current_user)]) -> AuthenticatedUser:
    return user
