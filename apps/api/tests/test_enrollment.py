from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.api.app.enrollment import (
    EnrollmentError,
    EnrollmentService,
    Heartbeat,
    InMemoryEnrollmentStore,
)


def test_enrollment_token_is_single_use_and_credential_is_returned_once() -> None:
    organization_id = uuid4()
    service = EnrollmentService(InMemoryEnrollmentStore())
    now = datetime(2026, 7, 24, tzinfo=UTC)
    token = service.issue_token(organization_id, now)
    result = service.enroll(token, organization_id, "0.1.0", now + timedelta(minutes=1))
    assert result.device_credential.startswith("gswg_device_")
    assert result.device_id in service.store.devices
    with pytest.raises(EnrollmentError, match="invalid_or_expired_token"):
        service.enroll(token, organization_id, "0.1.0", now + timedelta(minutes=2))


def test_concurrent_consumers_only_one_can_enroll() -> None:
    organization_id = uuid4()
    service = EnrollmentService(InMemoryEnrollmentStore())
    now = datetime(2026, 7, 24, tzinfo=UTC)
    token = service.issue_token(organization_id, now)

    def attempt():
        try:
            return service.enroll(token, organization_id, "0.1.0", now + timedelta(minutes=1))
        except EnrollmentError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(result != "invalid_or_expired_token" for result in results) == 1


def test_heartbeat_requires_valid_credential_and_recent_timezone_timestamp() -> None:
    organization_id = uuid4()
    service = EnrollmentService(InMemoryEnrollmentStore())
    now = datetime(2026, 7, 24, tzinfo=UTC)
    token = service.issue_token(organization_id, now)
    enrollment = service.enroll(token, organization_id, "0.1.0", now)
    heartbeat = Heartbeat(observed_at=now + timedelta(minutes=1), agent_version="0.1.1")
    result = service.heartbeat(enrollment.device_credential, heartbeat, now + timedelta(minutes=1))
    assert result.device_id == enrollment.device_id
    assert service.store.devices[result.device_id].status == "online"
    with pytest.raises(EnrollmentError, match="invalid_device_credential"):
        service.heartbeat("wrong", heartbeat, now + timedelta(minutes=1))
