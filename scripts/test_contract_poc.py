"""Dependency-free compatibility test runner for the Phase 1C contract POC."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.contracts.poc.source import ApiError, HealthResponse  # noqa: E402


def main() -> int:
    health = json.loads((ROOT / "packages/contracts/fixtures/health-response.json").read_text())
    error = json.loads((ROOT / "packages/contracts/fixtures/api-error.json").read_text())
    parsed_health = HealthResponse.model_validate(health)
    parsed_error = ApiError.model_validate(error)
    assert parsed_health.status.value == "healthy"
    assert parsed_health.detail is None
    assert parsed_error.code == "device_offline"
    assert parsed_error.details is None
    print("Contract POC compatibility tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
