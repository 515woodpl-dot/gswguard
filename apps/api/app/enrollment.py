from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EnrollmentError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class Heartbeat(BaseModel):
    observed_at: datetime
    agent_version: str = Field(min_length=1, max_length=40)


class EnrollmentResult(BaseModel):
    device_id: UUID
    device_credential: str
    enrolled_at: datetime


class HeartbeatResult(BaseModel):
    device_id: UUID
    status: str
    accepted_at: datetime


@dataclass(frozen=True)
class EnrollmentTokenRecord:
    token_hash: str
    organization_id: UUID
    expires_at: datetime


@dataclass
class DeviceRecord:
    device_id: UUID
    organization_id: UUID
    credential_hash: str
    status: str
    enrolled_at: datetime
    last_heartbeat_at: datetime | None = None
    agent_version: str = ""


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class InMemoryEnrollmentStore:
    """Thread-safe fake for protocol tests; not a production persistence adapter."""

    def __init__(self) -> None:
        self.tokens: dict[str, EnrollmentTokenRecord] = {}
        self.devices: dict[UUID, DeviceRecord] = {}
        self._lock = Lock()

    def add_token(self, record: EnrollmentTokenRecord) -> None:
        with self._lock:
            self.tokens[record.token_hash] = record

    def consume_token(self, token_hash: str, organization_id: UUID, now: datetime) -> EnrollmentTokenRecord:
        with self._lock:
            record = self.tokens.get(token_hash)
            if record is None or record.expires_at <= now or record.organization_id != organization_id:
                raise EnrollmentError("invalid_or_expired_token")
            del self.tokens[token_hash]
            return record

    def add_device(self, record: DeviceRecord) -> None:
        with self._lock:
            self.devices[record.device_id] = record

    def authenticate_device(self, credential: str) -> DeviceRecord:
        credential_hash = hash_secret(credential)
        with self._lock:
            for device in self.devices.values():
                if hmac.compare_digest(device.credential_hash, credential_hash):
                    if device.status == "revoked":
                        raise EnrollmentError("device_revoked")
                    return device
        raise EnrollmentError("invalid_device_credential")

    def update_heartbeat(self, device_id: UUID, heartbeat: Heartbeat) -> None:
        with self._lock:
            device = self.devices[device_id]
            device.last_heartbeat_at = heartbeat.observed_at
            device.agent_version = heartbeat.agent_version
            device.status = "online"


class EnrollmentService:
    def __init__(self, store: InMemoryEnrollmentStore, token_ttl: timedelta = timedelta(hours=1)):
        self.store = store
        self.token_ttl = token_ttl

    def issue_token(self, organization_id: UUID, now: datetime | None = None) -> str:
        issued_at = now or datetime.now(UTC)
        raw_token = f"yorg_enroll_{secrets.token_urlsafe(32)}"
        self.store.add_token(
            EnrollmentTokenRecord(
                token_hash=hash_secret(raw_token),
                organization_id=organization_id,
                expires_at=issued_at + self.token_ttl,
            )
        )
        return raw_token

    def enroll(
        self,
        raw_token: str,
        organization_id: UUID,
        agent_version: str,
        now: datetime | None = None,
    ) -> EnrollmentResult:
        enrolled_at = now or datetime.now(UTC)
        record = self.store.consume_token(hash_secret(raw_token), organization_id, enrolled_at)
        credential = f"yorg_device_{secrets.token_urlsafe(32)}"
        device_id = uuid4()
        self.store.add_device(
            DeviceRecord(
                device_id=device_id,
                organization_id=organization_id,
                credential_hash=hash_secret(credential),
                status="online",
                enrolled_at=enrolled_at,
                last_heartbeat_at=enrolled_at,
                agent_version=agent_version,
            )
        )
        return EnrollmentResult(
            device_id=device_id,
            device_credential=credential,
            enrolled_at=enrolled_at,
        )

    def heartbeat(
        self,
        credential: str,
        payload: Heartbeat,
        now: datetime | None = None,
        max_clock_skew: timedelta = timedelta(minutes=5),
    ) -> HeartbeatResult:
        accepted_at = now or datetime.now(UTC)
        observed_at = payload.observed_at
        if observed_at.tzinfo is None:
            raise EnrollmentError("heartbeat_timestamp_must_have_timezone")
        if abs(accepted_at - observed_at) > max_clock_skew:
            raise EnrollmentError("heartbeat_clock_skew")
        device = self.store.authenticate_device(credential)
        self.store.update_heartbeat(device.device_id, payload)
        return HeartbeatResult(
            device_id=device.device_id,
            status="online",
            accepted_at=accepted_at,
        )
