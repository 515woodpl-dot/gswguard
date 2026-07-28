from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.membership import MembershipLookupError


def test_membership_backend_outage_returns_503(monkeypatch) -> None:
    secret = "membership-outage-secret"
    app.state.jwt_verifier.secret = secret
    token = jwt.encode(
        {"sub": str(uuid4()), "aud": "authenticated", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        secret,
        algorithm="HS256",
    )

    class FailingRepository:
        def resolve(self, _user_id):
            raise MembershipLookupError("simulated outage")

    previous = app.state.membership_repository
    app.state.membership_repository = FailingRepository()
    try:
        response = TestClient(app).get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.state.membership_repository = previous
    assert response.status_code == 503
    assert response.json()["detail"] == "Authorization backend unavailable"
