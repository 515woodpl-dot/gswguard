from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from packages.contracts.poc.source import ApiError, HealthResponse, HealthStatus
from pydantic import ValidationError

from .config import Settings
from .auth import AuthenticatedUser, JwtVerifier, current_user
from .security import InProcessSlidingWindowLimiter, RateLimitMiddleware, SecurityHeadersMiddleware
from .membership import MembershipRepository
from .devices import DeviceEnrollmentRequest, DeviceRepository, EnrollmentTokenRequest, device_credential
from .enrollment import EnrollmentError, Heartbeat
from .jobs import JobCreateRequest, JobFailureRequest, JobRepositoryError, JobRequest, JobResultRequest, PostgresJobRepository
from .inventory import InventoryRepository, InventorySubmission
from .compliance import ComplianceEvaluation, ComplianceRepository, PolicyCreateRequest, PolicyRepository, PolicyRepositoryError, PolicySummary

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
# Held on app.state so operators can inspect it and tests can reset it between
# cases. This limiter is still a single-process abuse brake, not a multi-instance
# control, and behind a loopback reverse proxy every client shares one bucket.
app.state.rate_limiter = InProcessSlidingWindowLimiter()
app.add_middleware(
    RateLimitMiddleware,
    trusted_proxy_hops=settings.trusted_proxy_hops,
    limiter=app.state.rate_limiter,
)
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
app.state.job_repository = PostgresJobRepository(settings.database_url) if settings.database_url else None
app.state.inventory_repository = InventoryRepository(settings.database_url) if settings.database_url else None
app.state.policy_repository = PolicyRepository(settings.database_url) if settings.database_url else None
app.state.compliance_repository = ComplianceRepository(settings.database_url) if settings.database_url else None


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


def job_repository(request: Request) -> PostgresJobRepository:
    repository = request.app.state.job_repository
    if repository is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    return repository


def inventory_repository(request: Request) -> InventoryRepository:
    repository = request.app.state.inventory_repository
    if repository is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    return repository


def policy_repository(request: Request) -> PolicyRepository:
    repository = request.app.state.policy_repository
    if repository is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    return repository


def compliance_repository(request: Request) -> ComplianceRepository:
    repository = request.app.state.compliance_repository
    if repository is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    return repository


def map_enrollment_error(error: EnrollmentError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error.code)


def device_credential_header(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    """Resolve a device credential from the Authorization header.

    Declared optional so a missing header is an authentication failure (401)
    rather than a request-validation failure (422), and so a human `Bearer`
    token can never be accepted where a `Device` credential is required.
    """
    try:
        return device_credential(authorization)
    except EnrollmentError as error:
        raise map_enrollment_error(error) from error


def map_job_error(error: JobRepositoryError) -> HTTPException:
    if error.code == "device_not_found":
        return HTTPException(status_code=404, detail=error.code)
    if error.code == "job_not_claimed_or_device_unauthorized":
        return HTTPException(status_code=401, detail="Device is not authorized for this job")
    return HTTPException(status_code=409, detail=error.code)


def map_policy_error(error: PolicyRepositoryError) -> HTTPException:
    if error.code == "policy_conflict":
        return HTTPException(status_code=409, detail=error.code)
    return HTTPException(status_code=500, detail=error.code)


@app.get("/api/v1/devices", response_model=list, tags=["devices"])
async def devices(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[DeviceRepository, Depends(device_repository)],
) -> list:
    if user.organization_id is None:
        raise HTTPException(status_code=403, detail="Organization membership required")
    return repository.list_devices(user.organization_id)


@app.get("/api/v1/inventory/latest", tags=["inventory"])
async def latest_inventory(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[InventoryRepository, Depends(inventory_repository)],
) -> list[dict[str, object]]:
    if user.organization_id is None:
        raise HTTPException(status_code=403, detail="Organization membership required")
    return repository.latest_for_organization(user.organization_id)


@app.get("/api/v1/compliance/policies", tags=["compliance"])
async def list_compliance_policies(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[PolicyRepository, Depends(policy_repository)],
) -> list[PolicySummary]:
    if user.organization_id is None:
        raise HTTPException(status_code=403, detail="Organization membership required")
    return repository.list_for_organization(user.organization_id)


@app.post("/api/v1/compliance/policies", tags=["compliance"])
async def create_compliance_policy(
    payload: PolicyCreateRequest,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[PolicyRepository, Depends(policy_repository)],
) -> PolicySummary:
    if user.organization_id is None or user.role not in {"owner", "administrator"}:
        raise HTTPException(status_code=403, detail="Owner or administrator role required")
    try:
        return repository.create(user.organization_id, payload)
    except PolicyRepositoryError as error:
        raise map_policy_error(error) from error


@app.get("/api/v1/compliance/latest", tags=["compliance"])
async def latest_compliance(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[ComplianceRepository, Depends(compliance_repository)],
) -> list[ComplianceEvaluation]:
    if user.organization_id is None:
        raise HTTPException(status_code=403, detail="Organization membership required")
    return repository.latest_for_organization(user.organization_id)


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


@app.post("/api/v1/jobs", tags=["jobs"])
async def create_job(
    payload: JobCreateRequest,
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[PostgresJobRepository, Depends(job_repository)],
) -> dict[str, object]:
    if user.organization_id is None or user.role not in {"owner", "administrator"}:
        raise HTTPException(status_code=403, detail="Owner or administrator role required")
    try:
        request = JobRequest(
            organization_id=user.organization_id,
            device_id=payload.device_id,
            action_type=payload.action_type,
            action_payload=payload.action_payload,
            created_by=user.user_id,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
            expires_in_seconds=payload.expires_in_seconds,
            confirmed=payload.confirmed,
        )
        job = repository.create(request)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error
    except JobRepositoryError as error:
        raise map_job_error(error) from error
    return {
        "id": job.id,
        "device_id": job.request.device_id,
        "action_type": job.request.action_type,
        "status": job.status,
        "created_at": job.created_at,
        "expires_at": job.expires_at,
        "attempt_count": job.attempt_count,
    }


@app.get("/api/v1/jobs", tags=["jobs"])
async def list_jobs(
    user: Annotated[AuthenticatedUser, Depends(current_user)],
    repository: Annotated[PostgresJobRepository, Depends(job_repository)],
) -> list[dict[str, object]]:
    if user.organization_id is None:
        raise HTTPException(status_code=403, detail="Organization membership required")
    return [
        {
            "id": job.id,
            "device_id": job.request.device_id,
            "action_type": job.request.action_type,
            "status": job.status,
            "created_at": job.created_at,
            "expires_at": job.expires_at,
            "attempt_count": job.attempt_count,
            "error_code": job.error_code,
        }
        for job in repository.list_for_organization(user.organization_id)
    ]


@app.post("/api/v1/device/jobs/claim", tags=["jobs"])
async def claim_device_job(
    credential: Annotated[str, Depends(device_credential_header)],
    repository: Annotated[PostgresJobRepository, Depends(job_repository)],
) -> dict[str, object] | None:
    try:
        job = repository.claim_for_device(credential)
    except EnrollmentError as error:
        raise map_enrollment_error(error) from error
    if job is None:
        return None
    return {
        "id": job.id,
        "device_id": job.request.device_id,
        "action_type": job.request.action_type,
        "action_payload": job.request.action_payload,
        "status": job.status,
        "attempt_count": job.attempt_count,
        "claim_expires_at": job.claim_expires_at,
    }


@app.post("/api/v1/device/jobs/{job_id}/complete", tags=["jobs"])
async def complete_device_job(
    job_id: UUID,
    payload: JobResultRequest,
    credential: Annotated[str, Depends(device_credential_header)],
    repository: Annotated[PostgresJobRepository, Depends(job_repository)],
) -> dict[str, object]:
    try:
        job = repository.complete_for_device(credential, job_id, payload.result)
        return {"id": job.id, "status": job.status, "completed_at": datetime.now(UTC)}
    except EnrollmentError as error:
        raise map_enrollment_error(error) from error
    except JobRepositoryError as error:
        raise map_job_error(error) from error


@app.post("/api/v1/device/jobs/{job_id}/fail", tags=["jobs"])
async def fail_device_job(
    job_id: UUID,
    payload: JobFailureRequest,
    credential: Annotated[str, Depends(device_credential_header)],
    repository: Annotated[PostgresJobRepository, Depends(job_repository)],
) -> dict[str, object]:
    try:
        job = repository.fail_for_device(credential, job_id, payload.error_code)
        return {"id": job.id, "status": job.status, "completed_at": datetime.now(UTC)}
    except EnrollmentError as error:
        raise map_enrollment_error(error) from error
    except JobRepositoryError as error:
        raise map_job_error(error) from error


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
    credential: Annotated[str, Depends(device_credential_header)],
    repository: Annotated[DeviceRepository, Depends(device_repository)],
) -> object:
    try:
        return repository.heartbeat(credential, payload)
    except EnrollmentError as error:
        raise map_enrollment_error(error) from error


@app.post("/api/v1/devices/inventory", tags=["inventory"])
async def submit_inventory(
    payload: InventorySubmission,
    credential: Annotated[str, Depends(device_credential_header)],
    repository: Annotated[InventoryRepository, Depends(inventory_repository)],
) -> dict[str, object]:
    try:
        return repository.submit(credential, payload)
    except EnrollmentError as error:
        raise map_enrollment_error(error) from error
    except ValueError as error:
        raise map_enrollment_error(EnrollmentError(str(error))) from error
