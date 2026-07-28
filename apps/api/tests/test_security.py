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


def _production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "supabase_jwt_secret": "secret",
        "supabase_jwt_issuer": "https://example.supabase.co/auth/v1",
        "cors_origins": ["https://dashboard.example.com"],
    }
    values.update(overrides)
    return Settings(**values)


def test_production_rejects_wildcard_or_empty_cors() -> None:
    for origins in ([], ["*"]):
        try:
            _production_settings(cors_origins=origins).validate_for_production()
        except ValueError as error:
            assert "CORS_ORIGINS" in str(error)
        else:
            raise AssertionError("unsafe production CORS origins were accepted")


def test_security_headers_are_defined() -> None:
    assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"
    assert "geolocation=()" in SECURITY_HEADERS["Permissions-Policy"]
    assert "default-src 'none'" in SECURITY_HEADERS["Content-Security-Policy"]


def test_health_response_contains_security_headers() -> None:
    response = TestClient(app).get("/health/ready")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
