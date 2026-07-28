from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field

from .auth import AppRole
from .enrollment import EnrollmentError, EnrollmentResult, Heartbeat, HeartbeatResult, hash_secret


class EnrollmentTokenRequest(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    ttl_minutes: int = Field(default=60, ge=5, le=1440)


class DeviceEnrollmentRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    device_name: str = Field(min_length=1, max_length=160)
    manufacturer: str | None = Field(default=None, max_length=160)
    model: str | None = Field(default=None, max_length=160)
    serial_number: str | None = Field(default=None, max_length=160)
    agent_version: str = Field(min_length=1, max_length=40)
    platform: str = Field(default="unknown", pattern="^(windows|macos|ios|ipados|android|linux|unknown)$")
    os_version: str | None = Field(default=None, max_length=80)


class DeviceSummary(BaseModel):
    id: UUID
    device_name: str
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    agent_version: str
    platform: str
    os_version: str | None
    status: str
    enrolled_at: datetime
    last_heartbeat_at: datetime | None


class DeviceRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def issue_token(self, organization_id: UUID, created_by: UUID, request: EnrollmentTokenRequest) -> tuple[str, datetime]:
        import psycopg

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=request.ttl_minutes)
        raw_token = f"yorg_enroll_{secrets.token_urlsafe(32)}"
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                insert into public.enrollment_tokens
                  (organization_id, token_hash, label, created_by, expires_at)
                values (%s, %s, %s, %s, %s)
                """,
                (organization_id, hash_secret(raw_token), request.label, created_by, expires_at),
            )
            connection.commit()
        return raw_token, expires_at

    def enroll(self, request: DeviceEnrollmentRequest) -> EnrollmentResult:
        import psycopg

        now = datetime.now(UTC)
        credential = f"yorg_device_{secrets.token_urlsafe(32)}"
        try:
            with psycopg.connect(self.database_url) as connection:
                with connection.transaction():
                    token = connection.execute(
                        """
                        select id, organization_id
                        from public.enrollment_tokens
                        where token_hash = %s and consumed_at is null and expires_at > %s
                        for update
                        """,
                        (hash_secret(request.token), now),
                    ).fetchone()
                    if token is None:
                        raise EnrollmentError("invalid_or_expired_token")
                    token_id, organization_id = token
                    device_id = connection.execute(
                        """
                        insert into public.devices
                          (organization_id, device_name, manufacturer, model, serial_number,
                           agent_version, platform, os_version, credential_hash, status, enrolled_at, last_heartbeat_at)
                        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'online', %s, %s)
                        returning id
                        """,
                        (
                            organization_id,
                            request.device_name,
                            request.manufacturer,
                            request.model,
                            request.serial_number,
                            request.agent_version,
                            request.platform,
                            request.os_version,
                            hash_secret(credential),
                            now,
                            now,
                        ),
                    ).fetchone()[0]
                    connection.execute(
                        """
                        update public.enrollment_tokens
                        set consumed_at = %s, consumed_device_id = %s
                        where id = %s
                        """,
                        (now, device_id, token_id),
                    )
        except EnrollmentError:
            raise
        except psycopg.errors.UniqueViolation as exc:
            raise EnrollmentError("device_already_exists") from exc
        return EnrollmentResult(device_id=device_id, device_credential=credential, enrolled_at=now)

    def heartbeat(self, credential: str, payload: Heartbeat) -> HeartbeatResult:
        import psycopg

        accepted_at = datetime.now(UTC)
        if payload.observed_at.tzinfo is None or abs(accepted_at - payload.observed_at) > timedelta(minutes=5):
            raise EnrollmentError("heartbeat_clock_skew")
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    update public.devices
                    set status = 'online', agent_version = %s, last_heartbeat_at = %s, updated_at = %s
                    where credential_hash = %s and status <> 'revoked'
                    returning id
                    """,
                    (payload.agent_version, payload.observed_at, accepted_at, hash_secret(credential)),
                ).fetchone()
                if row is None:
                    raise EnrollmentError("invalid_device_credential")
        return HeartbeatResult(device_id=row[0], status="online", accepted_at=accepted_at)

    def list_devices(self, organization_id: UUID) -> list[DeviceSummary]:
        import psycopg

        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                """
                select id, device_name, manufacturer, model, serial_number, agent_version, platform, os_version,
                       case when status = 'online' and (last_heartbeat_at is null or last_heartbeat_at < now() - interval '5 minutes')
                            then 'offline' else status::text end as effective_status,
                       enrolled_at, last_heartbeat_at
                from public.devices
                where organization_id = %s
                order by device_name asc
                """,
                (organization_id,),
            ).fetchall()
        return [DeviceSummary(*row) for row in rows]


def device_credential(authorization: str) -> str:
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "device" or not credential:
        raise EnrollmentError("device_credential_required")
    return credential
