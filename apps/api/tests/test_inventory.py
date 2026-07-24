from datetime import UTC, datetime

from apps.api.app.inventory import (
    CpuInfo,
    InstalledSoftware,
    InventorySnapshot,
    LocalAccount,
    NetworkAdapter,
    SecurityPosture,
    StorageDevice,
    WindowsInfo,
    inventory_hash,
    software_changes,
)


def snapshot(version: str = "1.0.0", include_removed: bool = False) -> InventorySnapshot:
    software = [InstalledSoftware(name="GSW Tool", publisher="Golden Stone Works", version=version)]
    if include_removed:
        software.append(InstalledSoftware(name="Old Tool", publisher="Example", version="2.0"))
    return InventorySnapshot(
        device_name="GSW-LAPTOP-01",
        manufacturer="Example",
        model="Pro",
        serial_number="SERIAL-01",
        windows=WindowsInfo(edition="Windows 11 Pro", version="24H2", build="26100", update_status="current"),
        cpu=CpuInfo(name="Example CPU", logical_processors=8),
        installed_ram_bytes=16_000_000_000,
        storage=[StorageDevice(name="C:", capacity_bytes=500, free_bytes=200)],
        network_adapters=[NetworkAdapter(name="Ethernet", mac_address="00:11:22:33:44:55")],
        security=SecurityPosture(bitlocker="on", firewall="on", defender="healthy", secure_boot="on", tpm="ready", automatic_updates="on"),
        local_accounts=[LocalAccount(name="employee", account_type="local", is_administrator=False)],
        software=software,
        agent_version="0.1.0",
        last_heartbeat=datetime(2026, 7, 24, tzinfo=UTC),
    )


def test_inventory_hash_is_stable_and_changes_when_inventory_changes() -> None:
    assert inventory_hash(snapshot()) == inventory_hash(snapshot())
    assert inventory_hash(snapshot()) != inventory_hash(snapshot("1.1.0"))


def test_software_diff_detects_add_remove_and_version_change() -> None:
    changes = software_changes(snapshot(include_removed=True), snapshot("1.1.0"))
    assert {(change.software_key, change.change_type.value) for change in changes} == {
        ("golden stone works:gsw tool", "version_changed"),
        ("example:old tool", "removed"),
    }


def test_inventory_model_rejects_unapproved_surveillance_fields() -> None:
    payload = snapshot().model_dump()
    payload["browser_history"] = []
    try:
        InventorySnapshot.model_validate(payload)
    except ValueError as error:
        assert "browser_history" in str(error)
    else:
        raise AssertionError("prohibited inventory field was accepted")
