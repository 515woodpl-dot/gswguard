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
