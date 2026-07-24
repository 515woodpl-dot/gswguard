from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.api.app.jobs import (
    ActionType,
    InMemoryJobStore,
    JobRequest,
    JobService,
    JobStatus,
)


def request(action_type=ActionType.lock_screen, **kwargs) -> JobRequest:
    kwargs.setdefault("idempotency_key", "job-key-001")
    return JobRequest(
        organization_id=uuid4(),
        device_id=uuid4(),
        action_type=action_type,
        confirmed=True,
        **kwargs,
    )


def test_sensitive_actions_require_reason_and_payload_is_strict() -> None:
    with pytest.raises(ValueError, match="reason is required"):
        request(ActionType.restart)
    with pytest.raises(ValueError):
        request(ActionType.lock_screen, action_payload={"shell": "powershell"})
    command = request(ActionType.restart, reason="maintenance", action_payload={"grace_period_seconds": 30})
    assert command.action_payload == {"grace_period_seconds": 30}


def test_idempotency_returns_same_job_and_atomic_claim_allows_one_consumer() -> None:
    store = InMemoryJobStore()
    service = JobService(store)
    fixed = datetime(2026, 7, 24, tzinfo=UTC)
    first_request = request()
    first = service.submit(first_request, fixed)
    second = service.submit(first_request, fixed + timedelta(seconds=1))
    assert first.id == second.id
    claimed = service.claim_for_device(first_request.device_id, fixed)
    assert claimed and claimed.status == JobStatus.claimed
    assert service.claim_for_device(first_request.device_id, fixed) is None


def test_jobs_expire_before_claim_and_complete_with_structured_result() -> None:
    store = InMemoryJobStore()
    service = JobService(store)
    fixed = datetime(2026, 7, 24, tzinfo=UTC)
    job_request = request(expires_in_seconds=60)
    job = service.submit(job_request, fixed)
    assert service.claim_for_device(job_request.device_id, fixed + timedelta(seconds=61)) is None
    assert store.jobs[job.id].status == JobStatus.expired

    active_request = request(idempotency_key="job-key-002")
    active = service.submit(active_request, fixed)
    claimed = service.claim_for_device(active_request.device_id, fixed)
    assert claimed
    result = service.complete(active.id, {"code": "ok", "message": "completed"})
    assert result.status == JobStatus.succeeded
