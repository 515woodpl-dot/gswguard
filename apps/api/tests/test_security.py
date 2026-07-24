from apps.api.app.config import Settings
from apps.api.app.main import app
from apps.api.app.security import SECURITY_HEADERS
from fastapi.testclient import TestClient


def test_production_requires_jwt_configuration() -> None:
    try:
        Settings(app_env="production").validate_for_production()
    except ValueError as error:
        assert "SUPABASE_JWT_SECRET" in str(error)
    else:
        raise AssertionError("production configuration was accepted without JWT settings")


def test_security_headers_are_defined() -> None:
    assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"
    assert "geolocation=()" in SECURITY_HEADERS["Permissions-Policy"]


def test_health_response_contains_security_headers() -> None:
    response = TestClient(app).get("/health/ready")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
