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


def test_ready_reports_database_failure_without_leaking_connection_details(monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    class FailedConnection:
        def __enter__(self):
            raise RuntimeError("postgres://secret-password@example.invalid")

        def __exit__(self, *_args):
            return False

    class FakePsycopg:
        @staticmethod
        def connect(*_args, **_kwargs):
            return FailedConnection()

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=FakePsycopg.connect))
    from apps.api.app import main

    monkeypatch.setattr(main.settings, "database_url", "postgresql://redacted")
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["detail"] == "database unavailable"
    assert "secret-password" not in response.text
