from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.api.app.inventory import InstalledSoftware
from apps.api.app.software_monitor import (
    InMemorySoftwareMonitorStore,
    SoftwareMonitor,
    SoftwareScanScheduler,
    SoftwareScanSettings,
)
from apps.api.tests.test_inventory import snapshot


def test_scan_records_changes_and_deduplicates_notifications() -> None:
    store = InMemorySoftwareMonitorStore()
    monitor = SoftwareMonitor(store)
    organization_id = uuid4()
    device_id = uuid4()
    monitor.scan(organization_id, device_id, snapshot("1.0.0"))
    changes = monitor.scan(organization_id, device_id, snapshot("1.1.0"))
    assert len(changes) == 1
    assert len(store.notifications) == 2  # dashboard and email
    monitor.scan(organization_id, device_id, snapshot("1.1.0"))
    assert len(store.notifications) == 2


def test_scheduler_has_default_fifteen_minute_interval_and_jitter() -> None:
    scheduler = SoftwareScanScheduler(SoftwareScanSettings(jitter_seconds=0))
    last = datetime(2026, 7, 24, tzinfo=UTC)
    assert scheduler.next_due(last) == last + timedelta(minutes=15)
    assert not scheduler.due(last, last + timedelta(minutes=14))
    assert scheduler.due(last, last + timedelta(minutes=15))
