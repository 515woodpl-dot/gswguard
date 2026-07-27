from fastapi.testclient import TestClient

from apps.api.app.main import app


client = TestClient(app)


def test_live_health_is_structured_and_versioned() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "yorguard-api"
    assert body["request_id"]


def test_ready_health_is_available_under_api_v1() -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
