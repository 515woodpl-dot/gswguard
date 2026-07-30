"""Shared fixtures for API tests.

The app wires its repositories onto `app.state` at import time, so tests that
need fakes have to swap those slots. Doing that by hand leaks state between
modules: `test_auth.py` and `test_membership.py` both assign
`app.state.jwt_verifier.secret` and only one of them restores it, which makes
the suite order-dependent. `isolated_app` snapshots and restores every slot the
tests touch, so any module using it is order-independent.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.main import app

TEST_JWT_SECRET = "authorization-boundary-test-secret"

_STATE_SLOTS = (
    "membership_repository",
    "device_repository",
    "job_repository",
    "inventory_repository",
    "policy_repository",
    "compliance_repository",
)


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Iterator[None]:
    """Keep cases independent of each other's request counts.

    The limiter keys on client host and TestClient always presents the same
    one, so without this a long parametrized module exhausts the 120 req/min
    window and later tests see 429 instead of the status they assert. That is
    the same single-bucket behaviour the API shows behind a loopback reverse
    proxy (audit finding M1), so it is reset here rather than raised.
    """
    limiter = getattr(app.state, "rate_limiter", None)
    if limiter is not None:
        limiter.reset()
    yield


@pytest.fixture
def isolated_app() -> Iterator[FastAPI]:
    """Yield the app with every mutated state slot restored afterwards."""
    saved_slots = {slot: getattr(app.state, slot, None) for slot in _STATE_SLOTS}
    saved_secret = app.state.jwt_verifier.secret
    app.state.jwt_verifier.secret = TEST_JWT_SECRET
    try:
        yield app
    finally:
        app.state.jwt_verifier.secret = saved_secret
        for slot, value in saved_slots.items():
            setattr(app.state, slot, value)


@pytest.fixture
def client(isolated_app: FastAPI) -> TestClient:
    return TestClient(isolated_app)


def user_token(
    user_id: UUID | None = None,
    *,
    role: str | None = None,
    organization_id: UUID | None = None,
    expires_in_minutes: int = 5,
) -> str:
    """Mint an HS256 token shaped like a Supabase access token.

    `role` and `organization_id` are the *claims*. They are deliberately
    settable so tests can prove the API ignores them in favour of the
    database-backed membership lookup.
    """
    claims: dict[str, object] = {
        "sub": str(user_id or uuid4()),
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(minutes=expires_in_minutes),
    }
    if role is not None:
        claims["role"] = role
    if organization_id is not None:
        claims["organization_id"] = str(organization_id)
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


class FakeMembership:
    """Stand-in for the database-backed membership boundary."""

    def __init__(self, role: str, organization_id: UUID):
        self.role = role
        self.organization_id = organization_id
        self.lookups: list[UUID] = []

    def resolve(self, user_id: UUID):
        self.lookups.append(user_id)
        return (self.role, self.organization_id)


class NoMembership:
    def resolve(self, _user_id: UUID):
        return None
