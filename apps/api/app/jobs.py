from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ActionType(StrEnum):
    refresh_inventory = "refresh_inventory"
    lock_screen = "lock_screen"
    restart = "restart"
    install_software = "install_software"
    uninstall_software = "uninstall_software"
    windows_update = "windows_update"
    defender_quick_scan = "defender_quick_scan"
    remediation = "remediation"


class JobStatus(StrEnum):
    pending = "pending"
    claimed = "claimed"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    expired = "expired"
    cancelled = "cancelled"


SENSITIVE_ACTIONS = {
    ActionType.restart,
    ActionType.uninstall_software,
    ActionType.windows_update,
    ActionType.remediation,
}


class ActionPayload(BaseModel):
    model_config = {"extra": "forbid"}


class EmptyPayload(ActionPayload):
    pass


class RestartPayload(ActionPayload):
    grace_period_seconds: int = Field(default=60, ge=0, le=3600)


class SoftwarePayload(ActionPayload):
    package_id: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9._-]+$")
    version: str | None = Field(default=None, max_length=80)


class RemediationPayload(ActionPayload):
    policy_id: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9._-]+$")


def validate_payload(action_type: ActionType, payload: dict[str, Any]) -> dict[str, Any]:
    model: type[ActionPayload]
    if action_type == ActionType.restart:
        model = RestartPayload
    elif action_type in {ActionType.install_software, ActionType.uninstall_software}:
        model = SoftwarePayload
    elif action_type == ActionType.remediation:
        model = RemediationPayload
    else:
        model = EmptyPayload
    return model.model_validate(payload).model_dump(exclude_none=True)


class JobRequest(BaseModel):
    organization_id: UUID
    device_id: UUID
    action_type: ActionType
    action_payload: dict[str, Any] = Field(default_factory=dict)
    created_by: UUID | None = None
    reason: str | None = Field(default=None, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=160)
    expires_in_seconds: int = Field(default=86_400, ge=60, le=604_800)
    confirmed: bool = False

    @model_validator(mode="after")
    def validate_command(self) -> "JobRequest":
        if not self.confirmed:
            raise ValueError("job confirmation is required")
        if self.action_type in SENSITIVE_ACTIONS and not self.reason:
            raise ValueError("reason is required for sensitive actions")
        self.action_payload = validate_payload(self.action_type, self.action_payload)
        return self


class JobCreateRequest(BaseModel):
    device_id: UUID
    action_type: ActionType
    action_payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=160)
    expires_in_seconds: int = Field(default=86_400, ge=60, le=604_800)
    confirmed: bool = False


class JobResultRequest(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)


class JobFailureRequest(BaseModel):
    error_code: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9._-]+$")


@dataclass
class Job:
    id: UUID
    request: JobRequest
    status: JobStatus
    created_at: datetime
    expires_at: datetime
    attempt_count: int = 0
    claim_expires_at: datetime | None = None
    result: dict[str, Any] | None = None
    error_code: str | None = None


class JobRepositoryError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class PostgresJobRepository:
    """Transactional PostgreSQL job adapter used by the API and agents."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    @staticmethod
    def _job_from_row(row) -> Job:
        request = JobRequest(
            organization_id=row[1],
            device_id=row[2],
            action_type=row[3],
            action_payload=row[4] or {},
            created_by=row[5],
            reason=row[6],
            idempotency_key=row[7],
            expires_in_seconds=max(60, int((row[9] - row[8]).total_seconds())),
            confirmed=True,
        )
        return Job(
            id=row[0],
            request=request,
            status=JobStatus(row[10]),
            created_at=row[8],
            expires_at=row[9],
            attempt_count=row[11],
            claim_expires_at=row[12],
            result=row[13],
            error_code=row[14],
        )

    def create(self, request: JobRequest, now: datetime | None = None) -> Job:
        import psycopg
        from psycopg.types.json import Jsonb

        created_at = now or datetime.now(UTC)
        expires_at = created_at + timedelta(seconds=request.expires_in_seconds)
        columns = "id, organization_id, device_id, action_type, action_payload, created_by, reason, idempotency_key, created_at, expires_at, status, attempt_count, claim_expires_at, result, error_code"
        try:
            with psycopg.connect(self.database_url) as connection:
                with connection.transaction():
                    device = connection.execute(
                        "select organization_id, status::text from public.devices where id = %s for share",
                        (request.device_id,),
                    ).fetchone()
                    if device is None or device[0] != request.organization_id or device[1] == "revoked":
                        raise JobRepositoryError("device_not_found")
                    row = connection.execute(
                        f"""
                        insert into public.jobs
                          (organization_id, device_id, action_type, action_payload, created_by, reason,
                           idempotency_key, confirmation_at, expires_at, status)
                        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                        on conflict (organization_id, device_id, idempotency_key) do nothing
                        returning {columns}
                        """,
                        (
                            request.organization_id,
                            request.device_id,
                            request.action_type.value,
                            Jsonb(request.action_payload),
                            request.created_by,
                            request.reason,
                            request.idempotency_key,
                            created_at if request.confirmed else None,
                            expires_at,
                        ),
                    ).fetchone()
                    created_new = row is not None
                    if row is None:
                        row = connection.execute(
                            f"select {columns} from public.jobs where organization_id = %s and device_id = %s and idempotency_key = %s",
                            (request.organization_id, request.device_id, request.idempotency_key),
                        ).fetchone()
                    if row is None:
                        raise JobRepositoryError("job_create_failed")
                    if created_new:
                        from .audit import AuditOutcome, append_audit_in_transaction

                        append_audit_in_transaction(
                            connection,
                            organization_id=request.organization_id,
                            actor_type="user",
                            actor_id=request.created_by,
                            action="job.created",
                            outcome=AuditOutcome.accepted,
                            target_type="job",
                            target_id=row[0],
                            reason=request.reason,
                            metadata={"action_type": request.action_type.value},
                        )
                    return self._job_from_row(row)
        except JobRepositoryError:
            raise
        except psycopg.errors.UniqueViolation as exc:
            raise JobRepositoryError("job_conflict") from exc

    def list_for_organization(self, organization_id: UUID, limit: int = 100) -> list[Job]:
        import psycopg

        columns = "id, organization_id, device_id, action_type, action_payload, created_by, reason, idempotency_key, created_at, expires_at, status, attempt_count, claim_expires_at, result, error_code"
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                f"select {columns} from public.jobs where organization_id = %s order by created_at desc limit %s",
                (organization_id, limit),
            ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def claim_for_device(self, credential: str, lease_seconds: int = 120) -> Job | None:
        import psycopg

        from .enrollment import hash_secret

        columns = "j.id, j.organization_id, j.device_id, j.action_type, j.action_payload, j.created_by, j.reason, j.idempotency_key, j.created_at, j.expires_at, j.status, j.attempt_count, j.claim_expires_at, j.result, j.error_code"
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                connection.execute(
                    """
                    update public.jobs j
                    set status = 'pending', claim_expires_at = null
                    where j.status = 'claimed' and j.claim_expires_at < now()
                      and exists (select 1 from public.devices d where d.id = j.device_id and d.credential_hash = %s)
                    """,
                    (hash_secret(credential),),
                )
                row = connection.execute(
                    f"""
                    with candidate as (
                      select j.id
                      from public.jobs j
                      join public.devices d on d.id = j.device_id
                      where d.credential_hash = %s and d.status <> 'revoked'
                        and j.status = 'pending' and j.expires_at > now()
                        and j.attempt_count < j.max_attempts
                      order by j.created_at asc
                      for update of j skip locked
                      limit 1
                    )
                    update public.jobs j
                    set status = 'claimed', attempt_count = j.attempt_count + 1,
                        claimed_at = now(), claim_expires_at = now() + (%s * interval '1 second')
                    from candidate c
                    where j.id = c.id
                    returning {columns}
                    """,
                    (hash_secret(credential), lease_seconds),
                ).fetchone()
                if row:
                    from .audit import AuditOutcome, append_audit_in_transaction

                    append_audit_in_transaction(
                        connection,
                        organization_id=row[1],
                        actor_type="device",
                        actor_id=row[2],
                        action="job.claimed",
                        outcome=AuditOutcome.accepted,
                        target_type="job",
                        target_id=row[0],
                    )
                return self._job_from_row(row) if row else None

    def _finish_for_device(self, credential: str, job_id: UUID, *, result: dict[str, Any] | None = None, error_code: str | None = None) -> Job:
        import psycopg
        from psycopg.types.json import Jsonb

        from .enrollment import hash_secret

        columns = "j.id, j.organization_id, j.device_id, j.action_type, j.action_payload, j.created_by, j.reason, j.idempotency_key, j.created_at, j.expires_at, j.status, j.attempt_count, j.claim_expires_at, j.result, j.error_code"
        next_status = "succeeded" if error_code is None else "failed"
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                row = connection.execute(
                    f"""
                    update public.jobs j
                    set status = %s, completed_at = now(), result = %s, error_code = %s
                    where j.id = %s and j.status = 'claimed'
                      and exists (select 1 from public.devices d where d.id = j.device_id and d.credential_hash = %s and d.status <> 'revoked')
                    returning {columns}
                    """,
                    (next_status, Jsonb(result or {}), error_code, job_id, hash_secret(credential)),
                ).fetchone()
                if row is None:
                    raise JobRepositoryError("job_not_claimed_or_device_unauthorized")
                from .audit import AuditOutcome, append_audit_in_transaction

                append_audit_in_transaction(
                    connection,
                    organization_id=row[1],
                    actor_type="device",
                    actor_id=row[2],
                    action="job.completed" if error_code is None else "job.failed",
                    outcome=AuditOutcome.succeeded if error_code is None else AuditOutcome.failed,
                    target_type="job",
                    target_id=row[0],
                    metadata={"error_code": error_code} if error_code else {},
                )
                return self._job_from_row(row)

    def complete_for_device(self, credential: str, job_id: UUID, result: dict[str, Any]) -> Job:
        return self._finish_for_device(credential, job_id, result=result)

    def fail_for_device(self, credential: str, job_id: UUID, error_code: str) -> Job:
        return self._finish_for_device(credential, job_id, error_code=error_code)


class InMemoryJobStore:
    """Test-only store representing the transactional Postgres adapter."""

    def __init__(self) -> None:
        self.jobs: dict[UUID, Job] = {}
        self.by_idempotency: dict[tuple[UUID, UUID, str], UUID] = {}
        self._lock = Lock()

    def create(self, request: JobRequest, now: datetime) -> Job:
        key = (request.organization_id, request.device_id, request.idempotency_key)
        with self._lock:
            existing_id = self.by_idempotency.get(key)
            if existing_id:
                return self.jobs[existing_id]
            job = Job(uuid4(), request, JobStatus.pending, now, now + timedelta(seconds=request.expires_in_seconds))
            self.jobs[job.id] = job
            self.by_idempotency[key] = job.id
            return job

    def claim(self, device_id: UUID, now: datetime, lease: timedelta) -> Job | None:
        with self._lock:
            for job in sorted(self.jobs.values(), key=lambda item: item.created_at):
                if job.request.device_id != device_id:
                    continue
                if job.status == JobStatus.pending and job.expires_at <= now:
                    job.status = JobStatus.expired
                    continue
                if job.status != JobStatus.pending or job.expires_at <= now:
                    continue
                if job.attempt_count >= 3:
                    job.status = JobStatus.failed
                    job.error_code = "max_attempts_exceeded"
                    continue
                job.status = JobStatus.claimed
                job.attempt_count += 1
                job.claim_expires_at = now + lease
                return job
        return None


class JobService:
    def __init__(self, store: InMemoryJobStore):
        self.store = store

    def submit(self, request: JobRequest, now: datetime | None = None) -> Job:
        return self.store.create(request, now or datetime.now(UTC))

    def claim_for_device(self, device_id: UUID, now: datetime | None = None, lease_seconds: int = 120) -> Job | None:
        return self.store.claim(device_id, now or datetime.now(UTC), timedelta(seconds=lease_seconds))

    def complete(self, job_id: UUID, result: dict[str, Any], now: datetime | None = None) -> Job:
        with self.store._lock:
            job = self.store.jobs[job_id]
            if job.status != JobStatus.claimed:
                raise ValueError("job is not claimed")
            job.status = JobStatus.succeeded
            job.result = result
            return job

    def fail(self, job_id: UUID, error_code: str, now: datetime | None = None) -> Job:
        with self.store._lock:
            job = self.store.jobs[job_id]
            if job.status != JobStatus.claimed:
                raise ValueError("job is not claimed")
            job.status = JobStatus.failed
            job.error_code = error_code
            return job
