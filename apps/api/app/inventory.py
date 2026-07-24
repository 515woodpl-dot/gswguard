from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InventoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WindowsInfo(InventoryModel):
    edition: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=80)
    build: str = Field(min_length=1, max_length=40)
    update_status: str = Field(min_length=1, max_length=40)


class CpuInfo(InventoryModel):
    name: str = Field(min_length=1, max_length=160)
    logical_processors: int = Field(ge=1, le=512)


class StorageDevice(InventoryModel):
    name: str = Field(min_length=1, max_length=160)
    capacity_bytes: int = Field(ge=0)
    free_bytes: int = Field(ge=0)


class NetworkAdapter(InventoryModel):
    name: str = Field(min_length=1, max_length=160)
    mac_address: str = Field(min_length=1, max_length=32)
    ip_addresses: list[str] = Field(default_factory=list, max_length=16)


class SecurityPosture(InventoryModel):
    bitlocker: str = Field(min_length=1, max_length=40)
    firewall: str = Field(min_length=1, max_length=40)
    defender: str = Field(min_length=1, max_length=40)
    defender_signature_age_hours: int | None = Field(default=None, ge=0, le=8760)
    secure_boot: str = Field(min_length=1, max_length=40)
    tpm: str = Field(min_length=1, max_length=40)
    automatic_updates: str = Field(min_length=1, max_length=40)


class LocalAccount(InventoryModel):
    name: str = Field(min_length=1, max_length=160)
    account_type: str = Field(min_length=1, max_length=40)
    is_administrator: bool


class InstalledSoftware(InventoryModel):
    name: str = Field(min_length=1, max_length=240)
    publisher: str | None = Field(default=None, max_length=240)
    version: str = Field(min_length=1, max_length=80)
    architecture: str | None = Field(default=None, max_length=20)
    install_source: str | None = Field(default=None, max_length=80)

    @property
    def software_key(self) -> str:
        publisher = (self.publisher or "").strip().casefold()
        return f"{publisher}:{self.name.strip().casefold()}"


class InventorySnapshot(InventoryModel):
    device_name: str = Field(min_length=1, max_length=160)
    manufacturer: str = Field(min_length=1, max_length=160)
    model: str = Field(min_length=1, max_length=160)
    serial_number: str = Field(min_length=1, max_length=160)
    windows: WindowsInfo
    cpu: CpuInfo
    installed_ram_bytes: int = Field(ge=0)
    storage: list[StorageDevice] = Field(max_length=32)
    network_adapters: list[NetworkAdapter] = Field(max_length=64)
    security: SecurityPosture
    local_accounts: list[LocalAccount] = Field(max_length=128)
    software: list[InstalledSoftware] = Field(max_length=2000)
    agent_version: str = Field(min_length=1, max_length=40)
    startup_time: datetime | None = None
    last_heartbeat: datetime | None = None


class SoftwareChangeType(StrEnum):
    added = "added"
    removed = "removed"
    version_changed = "version_changed"


class SoftwareChange(InventoryModel):
    software_key: str
    change_type: SoftwareChangeType
    previous_version: str | None = None
    current_version: str | None = None


def canonical_inventory(snapshot: InventorySnapshot) -> dict[str, Any]:
    """Return stable JSON-ready data without collecting prohibited content."""
    return snapshot.model_dump(mode="json", exclude_none=True)


def inventory_hash(snapshot: InventorySnapshot) -> str:
    canonical = json.dumps(canonical_inventory(snapshot), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def software_changes(
    previous: InventorySnapshot | None, current: InventorySnapshot
) -> list[SoftwareChange]:
    before = {item.software_key: item for item in (previous.software if previous else [])}
    after = {item.software_key: item for item in current.software}
    changes: list[SoftwareChange] = []
    for key in sorted(after.keys() - before.keys()):
        changes.append(SoftwareChange(software_key=key, change_type=SoftwareChangeType.added, current_version=after[key].version))
    for key in sorted(before.keys() - after.keys()):
        changes.append(SoftwareChange(software_key=key, change_type=SoftwareChangeType.removed, previous_version=before[key].version))
    for key in sorted(after.keys() & before.keys()):
        if after[key].version != before[key].version:
            changes.append(
                SoftwareChange(
                    software_key=key,
                    change_type=SoftwareChangeType.version_changed,
                    previous_version=before[key].version,
                    current_version=after[key].version,
                )
            )
    return changes
