#!/usr/bin/env python3
"""Enroll a macOS development receiver and send YorGuard heartbeats."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


KEYCHAIN_SERVICE = "YorGuard Device Credential"


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


def main() -> None:
    parser = argparse.ArgumentParser(description="YorGuard macOS development receiver")
    parser.add_argument("--api-base-url", default=os.getenv("YORGUARD_API_BASE_URL", "http://100.127.37.0:8000"))
    parser.add_argument("--device-name", default=os.uname().nodename)
    parser.add_argument("--agent-version", default="0.1.0")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="send heartbeats repeatedly")
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
