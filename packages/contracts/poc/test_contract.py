import json
from pathlib import Path

from .source import ApiError, HealthResponse


ROOT = Path(__file__).resolve().parents[3]


def test_health_fixture_accepts_required_optional_nullable_fields() -> None:
    payload = json.loads(
        (ROOT / "packages/contracts/fixtures/health-response.json").read_text()
    )
    result = HealthResponse.model_validate(payload)
    assert result.status.value == "healthy"
    assert result.detail is None


def test_error_fixture_accepts_nullable_details() -> None:
    payload = json.loads((ROOT / "packages/contracts/fixtures/api-error.json").read_text())
    result = ApiError.model_validate(payload)
    assert result.code == "device_offline"
    assert result.details is None
