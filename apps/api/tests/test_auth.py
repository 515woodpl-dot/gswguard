from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from apps.api.app.main import app


def test_auth_rejects_missing_bearer_token() -> None:
    response = TestClient(app).get("/api/v1/auth/me")
    assert response.status_code == 401


def test_auth_verifies_supabase_style_hs256_claims(monkeypatch) -> None:
    secret = "phase-2-test-secret"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    app.state.jwt_verifier.secret = secret
    user_id = uuid4()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "viewer",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        secret,
        algorithm="HS256",
    )
    response = TestClient(app).get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == str(user_id)
    assert response.json()["role"] == "viewer"


def test_database_membership_boundary_does_not_fall_back_to_jwt_role(monkeypatch) -> None:
    secret = "membership-boundary-secret"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    app.state.jwt_verifier.secret = secret
    user_id = uuid4()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "owner",
            "organization_id": str(uuid4()),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        secret,
        algorithm="HS256",
    )

    class MissingMembership:
        def resolve(self, _user_id):
            return None

    previous = app.state.membership_repository
    app.state.membership_repository = MissingMembership()
    try:
        response = TestClient(app).get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.state.membership_repository = previous
    assert response.status_code == 403
    assert response.json()["detail"] == "Organization membership required"
