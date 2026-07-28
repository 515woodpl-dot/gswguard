#!/usr/bin/env python3
"""Enroll a macOS development receiver and send YorGuard heartbeats."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import plistlib
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


KEYCHAIN_SERVICE = "YorGuard Device Credential"
DEFAULT_API_BASE_URL = "https://gsw.tail8a6b99.ts.net:8443"


def request_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"YorGuard request failed ({error.code}): {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Unable to reach YorGuard: {error.reason}") from error


def keychain_read(account: str) -> str | None:
    result = subprocess.run(
        ["security", "find-generic-password", "-a", account, "-s", KEYCHAIN_SERVICE, "-w"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None if result.returncode == 0 else None


def keychain_write(account: str, credential: str) -> None:
    subprocess.run(
        ["security", "add-generic-password", "-a", account, "-s", KEYCHAIN_SERVICE, "-w", credential, "-U"],
        check=True,
        capture_output=True,
        text=True,
    )


def heartbeat(api_base_url: str, credential: str, agent_version: str) -> None:
    request_json(
        f"{api_base_url.rstrip('/')}/api/v1/devices/heartbeat",
        {"observed_at": datetime.now(timezone.utc).isoformat(), "agent_version": agent_version},
        {"Authorization": f"Device {credential}"},
    )


def run_text(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
    return result.stdout.strip() if result.returncode == 0 else ""


def collect_mac_inventory(device_name: str, agent_version: str) -> dict:
    os_version = run_text(["sw_vers", "-productVersion"]) or os.uname().release
    model = run_text(["sysctl", "-n", "hw.model"]) or "Mac"
    cpu_name = run_text(["sysctl", "-n", "machdep.cpu.brand_string"]) or model
    logical_processors = int(run_text(["sysctl", "-n", "hw.logicalcpu"]) or "1")
    ram_bytes = int(run_text(["sysctl", "-n", "hw.memsize"]) or "0")
    serial_output = run_text(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"])
    serial_number = "unknown"
    for line in serial_output.splitlines():
        if "IOPlatformSerialNumber" in line and "=" in line:
            serial_number = line.split("=", 1)[1].strip().strip('"') or "unknown"
            break
    disk = shutil.disk_usage("/")
    storage = [{"name": "/", "capacity_bytes": disk.total, "free_bytes": disk.free}]
    software = []
    for applications in ("/Applications", os.path.expanduser("~/Applications")):
        if not os.path.isdir(applications):
            continue
        for entry in os.listdir(applications):
            if not entry.endswith(".app"):
                continue
            info_path = os.path.join(applications, entry, "Contents", "Info.plist")
            try:
                with open(info_path, "rb") as info_file:
                    info = plistlib.load(info_file)
                software.append({
                    "name": str(info.get("CFBundleDisplayName") or info.get("CFBundleName") or entry[:-4]),
                    "publisher": None,
                    "version": str(info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or "unknown"),
                    "architecture": None,
                    "install_source": "Applications",
                })
            except (OSError, plistlib.InvalidFileException, ValueError):
                continue
            if len(software) >= 2000:
                break
    return {
        "snapshot": {
            "platform": "macos",
            "device_name": device_name,
            "manufacturer": "Apple",
            "model": model,
            "serial_number": serial_number,
            "os_version": os_version,
            "cpu": {"name": cpu_name, "logical_processors": max(1, logical_processors)},
            "installed_ram_bytes": max(0, ram_bytes),
            "storage": storage,
            "network_adapters": [],
            "security": {
                "bitlocker": "not_applicable",
                "firewall": "not_collected",
                "defender": "not_applicable",
                "secure_boot": "not_collected",
                "tpm": "not_collected",
                "automatic_updates": "not_collected",
            },
            "local_accounts": [{"name": getpass.getuser(), "account_type": "local", "is_administrator": False}],
            "software": software,
            "agent_version": agent_version,
        }
    }


def process_test_job(api_base_url: str, credential: str, device_name: str, agent_version: str) -> None:
    """Claim and acknowledge only the non-privileged inventory test action."""
    job = request_json(
        f"{api_base_url.rstrip('/')}/api/v1/device/jobs/claim",
        {},
        {"Authorization": f"Device {credential}"},
    )
    if not job:
        return
    job_id = job["id"]
    if job.get("action_type") == "refresh_inventory":
        request_json(
            f"{api_base_url.rstrip('/')}/api/v1/device/jobs/{job_id}/complete",
            {"result": {"code": "inventory_submitted"}},
            {"Authorization": f"Device {credential}"},
        )
        print(f"Acknowledged test job {job_id}")
    else:
        request_json(
            f"{api_base_url.rstrip('/')}/api/v1/device/jobs/{job_id}/fail",
            {"error_code": "unsupported_in_development_receiver"},
            {"Authorization": f"Device {credential}"},
        )
        print(f"Rejected unsupported job {job_id}")


def submit_inventory(api_base_url: str, credential: str, device_name: str, agent_version: str) -> None:
    request_json(
        f"{api_base_url.rstrip('/')}/api/v1/devices/inventory",
        collect_mac_inventory(device_name, agent_version),
        {"Authorization": f"Device {credential}"},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="YorGuard macOS development receiver")
    parser.add_argument("--api-base-url", default=os.getenv("YORGUARD_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--device-name", default=os.uname().nodename)
    parser.add_argument("--agent-version", default="0.1.0")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="send heartbeats repeatedly")
    parser.add_argument("--jobs", action="store_true", help="claim and acknowledge safe development jobs")
    args = parser.parse_args()
    account = getpass.getuser()
    credential = keychain_read(account)

    if credential is None:
        token = getpass.getpass("YorGuard enrollment token: ")
        enrollment = request_json(
            f"{args.api_base_url.rstrip('/')}/api/v1/devices/enroll",
            {
                "token": token,
                "device_name": args.device_name,
                "manufacturer": "Apple",
                "model": "Mac",
                "agent_version": args.agent_version,
                "platform": "macos",
                "os_version": os.uname().release,
            },
        )
        credential = enrollment["device_credential"]
        keychain_write(account, credential)
        print(f"Enrolled device {enrollment['device_id']}; credential stored in macOS Keychain.")

    retry_delay = 15
    while True:
        try:
            heartbeat(args.api_base_url, credential, args.agent_version)
            print(f"Heartbeat accepted at {datetime.now().astimezone().isoformat(timespec='seconds')}")
            if args.jobs:
                submit_inventory(args.api_base_url, credential, args.device_name, args.agent_version)
                print("Inventory snapshot submitted")
                process_test_job(args.api_base_url, credential, args.device_name, args.agent_version)
            retry_delay = 15
            if not args.watch:
                break
            time.sleep(args.watch)
        except (RuntimeError, OSError) as error:
            if not args.watch:
                raise
            print(f"YorGuard heartbeat failed: {error}; retrying in {retry_delay}s", file=sys.stderr)
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 300)


if __name__ == "__main__":
    main()
