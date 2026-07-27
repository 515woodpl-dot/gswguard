from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .inventory import InventorySnapshot, SoftwareChange, software_changes


class SoftwareScanSettings(BaseModel):
    interval_seconds: int = Field(default=900, ge=60, le=86_400)
    jitter_seconds: int = Field(default=30, ge=0, le=900)


class Notification(BaseModel):
    id: UUID
    organization_id: UUID
    device_id: UUID
    channel: str
    notification_key: str
    title: str
    body: str
    status: str = "pending"


class NotificationProvider(Protocol):
    def publish(self, notification: Notification) -> None: ...


class InMemorySoftwareMonitorStore:
    """Test-only store; production uses the Phase 5 PostgreSQL tables."""

    def __init__(self) -> None:
        self.latest: dict[UUID, InventorySnapshot] = {}
        self.notifications: list[Notification] = []
        self._notification_keys: set[tuple[str, str]] = set()
        self._lock = Lock()

    def save_snapshot(self, device_id: UUID, snapshot: InventorySnapshot) -> None:
        with self._lock:
            self.latest[device_id] = snapshot

    def create_notification(self, notification: Notification) -> bool:
        with self._lock:
            key = (notification.channel, notification.notification_key)
            if key in self._notification_keys:
                return False
            self._notification_keys.add(key)
            self.notifications.append(notification)
            return True


class SoftwareMonitor:
    def __init__(
        self,
        store: InMemorySoftwareMonitorStore,
        provider: NotificationProvider | None = None,
    ):
        self.store = store
        self.provider = provider
        self._device_locks: dict[UUID, Lock] = {}
        self._locks_guard = Lock()

    def _lock_for(self, device_id: UUID) -> Lock:
        with self._locks_guard:
            return self._device_locks.setdefault(device_id, Lock())

    def scan(self, organization_id: UUID, device_id: UUID, current: InventorySnapshot) -> list[SoftwareChange]:
        device_lock = self._lock_for(device_id)
        if not device_lock.acquire(blocking=False):
            return []
        try:
            previous = self.store.latest.get(device_id)
            # The first scan establishes a baseline and does not page on every
            # application already present before YorGuard enrollment.
            changes = software_changes(previous, current) if previous is not None else []
            self.store.save_snapshot(device_id, current)
            for change in changes:
                self._notify(organization_id, device_id, change)
            return changes
        finally:
            device_lock.release()

    def _notify(self, organization_id: UUID, device_id: UUID, change: SoftwareChange) -> None:
        version = change.current_version or change.previous_version or "unknown"
        key = f"{device_id}:{change.software_key}:{change.change_type.value}:{version}"
        title = f"Software {change.change_type.value.replace('_', ' ')}"
        body = f"{change.software_key} changed from {change.previous_version or 'not installed'} to {change.current_version or 'not installed'}."
        for channel in ("dashboard", "email"):
            notification = Notification(
                id=uuid4(),
                organization_id=organization_id,
                device_id=device_id,
                channel=channel,
                notification_key=key,
                title=title,
                body=body,
            )
            if self.store.create_notification(notification) and self.provider:
                self.provider.publish(notification)


class SoftwareScanScheduler:
    def __init__(self, settings: SoftwareScanSettings, random_source: random.Random | None = None):
        self.settings = settings
        self.random_source = random_source or random.Random()

    def next_due(self, last_scan: datetime, now: datetime | None = None) -> datetime:
        if last_scan.tzinfo is None:
            raise ValueError("last_scan must include timezone")
        jitter = self.random_source.randint(0, self.settings.jitter_seconds)
        return last_scan + timedelta(seconds=self.settings.interval_seconds + jitter)

    def due(self, last_scan: datetime, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        return current >= self.next_due(last_scan, current)
