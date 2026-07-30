"""HTTP-level authorization boundary tests. Audit finding C4.

Before these existed the suite reached only /health/live, /health/ready and
/api/v1/auth/me, so every organization-scoping check, every role gate and every
device-credential check in main.py was unverified.

The load-bearing assertions here are:

* organization scope comes from the database-backed membership lookup, never
  from a JWT claim or a request body (baseline threat model: "Services derive
  scope from authenticated context rather than trusting arbitrary
  client-supplied organization IDs");
* the `role` claim in a token is not authorization;
* a human `Bearer` token cannot be substituted for a device credential
  ("Device authentication is separate from human authentication").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from apps.api.app.compliance import PolicySummary, RuleKey
from apps.api.app.jobs import Job, JobRequest, JobStatus
from apps.api.tests.conftest import FakeMembership, NoMembership, user_token

DEVICE_JOB_ID = uuid4()

# (method, path, json body) for every route that requires a human session.
USER_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/v1/devices", None),
    ("GET", "/api/v1/inventory/latest", None),
    ("GET", "/api/v1/jobs", None),
    ("GET", "/api/v1/compliance/policies", None),
    ("GET", "/api/v1/compliance/latest", None),
    ("POST", "/api/v1/enrollment-tokens", {"label": "probe", "ttl_minutes": 15}),
    ("POST", "/api/v1/compliance/policies", {
        "policy_key": "probe-firewall",
        "name": "Probe",
        "rule_type": "firewall",
        "expected_value": "on",
    }),
    ("POST", "/api/v1/jobs", {
        "device_id": str(uuid4()),
        "action_type": "refresh_inventory",
        "idempotency_key": "probe-key-0001",
        "confirmed": True,
    }),
]

# Routes gated on owner/administrator in addition to organization membership.
ADMIN_ONLY_ROUTES = [route for route in USER_ROUTES if route[0] == "POST"]

# Routes authenticated by a device credential, not a human token.
DEVICE_ROUTES: list[tuple[str, str, dict[str, Any]]] = [
    ("POST", "/api/v1/device/jobs/claim", {}),
    ("POST", f"/api/v1/device/jobs/{DEVICE_JOB_ID}/complete", {"result": {}}),
    ("POST", f"/api/v1/device/jobs/{DEVICE_JOB_ID}/fail", {"error_code": "probe"}),
    ("POST", "/api/v1/devices/heartbeat", {
        "observed_at": datetime.now(UTC).isoformat(),
        "agent_version": "0.1.0",
    }),
    ("POST", "/api/v1/devices/inventory", {}),
]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def send(client, method: str, path: str, body: dict[str, Any] | None, headers: dict[str, str]):
    if method == "GET":
        return client.get(path, headers=headers)
    return client.post(path, json=body or {}, headers=headers)


# --------------------------------------------------------------------------- #
# Recording fakes. Each records the organization id it was handed, so a test
# can assert which scope the route actually used.
# --------------------------------------------------------------------------- #


@dataclass
class Recorder:
    organizations: list[UUID]

    def __init__(self) -> None:
        self.organizations = []
        self.job_requests: list[JobRequest] = []
        self.token_actors: list[UUID] = []


class FakeDeviceRepository:
    def __init__(self, recorder: Recorder):
        self.recorder = recorder

    def list_devices(self, organization_id: UUID) -> list:
        self.recorder.organizations.append(organization_id)
        return []

    def issue_token(self, organization_id: UUID, created_by: UUID, request) -> tuple[str, datetime]:
        self.recorder.organizations.append(organization_id)
        self.recorder.token_actors.append(created_by)
        return "yorg_enroll_probe", datetime.now(UTC) + timedelta(minutes=request.ttl_minutes)


class FakeInventoryRepository:
    def __init__(self, recorder: Recorder):
        self.recorder = recorder

    def latest_for_organization(self, organization_id: UUID) -> list[dict[str, object]]:
        self.recorder.organizations.append(organization_id)
        return []


class FakeJobRepository:
    def __init__(self, recorder: Recorder):
        self.recorder = recorder

    def list_for_organization(self, organization_id: UUID) -> list[Job]:
        self.recorder.organizations.append(organization_id)
        return []

    def create(self, request: JobRequest) -> Job:
        self.recorder.organizations.append(request.organization_id)
        self.recorder.job_requests.append(request)
        now = datetime.now(UTC)
        return Job(
            id=uuid4(),
            request=request,
            status=JobStatus.pending,
            created_at=now,
            expires_at=now + timedelta(seconds=request.expires_in_seconds),
        )


class FakePolicyRepository:
    def __init__(self, recorder: Recorder):
        self.recorder = recorder

    def list_for_organization(self, organization_id: UUID) -> list[PolicySummary]:
        self.recorder.organizations.append(organization_id)
        return []

    def create(self, organization_id: UUID, request) -> PolicySummary:
        self.recorder.organizations.append(organization_id)
        now = datetime.now(UTC)
        return PolicySummary(
            id=uuid4(),
            policy_key=request.policy_key,
            name=request.name,
            rule_type=RuleKey(request.rule_type),
            expected_value=request.expected_value,
            enabled=request.enabled,
            automatic_remediation=request.automatic_remediation,
            weight=request.weight,
            created_at=now,
            updated_at=now,
        )


class FakeComplianceRepository:
    def __init__(self, recorder: Recorder):
        self.recorder = recorder

    def latest_for_organization(self, organization_id: UUID) -> list:
        self.recorder.organizations.append(organization_id)
        return []


@pytest.fixture
def wired(isolated_app):
    """Install recording fakes for every repository and return the recorder."""
    recorder = Recorder()
    isolated_app.state.device_repository = FakeDeviceRepository(recorder)
    isolated_app.state.inventory_repository = FakeInventoryRepository(recorder)
    isolated_app.state.job_repository = FakeJobRepository(recorder)
    isolated_app.state.policy_repository = FakePolicyRepository(recorder)
    isolated_app.state.compliance_repository = FakeComplianceRepository(recorder)
    return recorder


# --------------------------------------------------------------------------- #
# Unauthenticated access
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("method", "path", "body"), USER_ROUTES)
def test_user_routes_reject_missing_token(client, wired, method, path, body) -> None:
    response = send(client, method, path, body, headers={})
    assert response.status_code == 401
    assert wired.organizations == []


@pytest.mark.parametrize(("method", "path", "body"), USER_ROUTES)
def test_user_routes_reject_garbage_token(client, wired, method, path, body) -> None:
    response = send(client, method, path, body, bearer("not-a-jwt"))
    assert response.status_code == 401
    assert wired.organizations == []


@pytest.mark.parametrize(("method", "path", "body"), USER_ROUTES)
def test_user_routes_reject_expired_token(client, wired, method, path, body) -> None:
    token = user_token(role="owner", organization_id=uuid4(), expires_in_minutes=-5)
    response = send(client, method, path, body, bearer(token))
    assert response.status_code == 401
    assert wired.organizations == []


@pytest.mark.parametrize(("method", "path", "body"), USER_ROUTES)
def test_user_routes_reject_token_signed_with_wrong_key(client, wired, method, path, body) -> None:
    import jwt as pyjwt

    token = pyjwt.encode(
        {
            "sub": str(uuid4()),
            "aud": "authenticated",
            "role": "owner",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "an-attacker-controlled-secret",
        algorithm="HS256",
    )
    response = send(client, method, path, body, bearer(token))
    assert response.status_code == 401
    assert wired.organizations == []


# --------------------------------------------------------------------------- #
# Organization scoping
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("method", "path", "body"), USER_ROUTES)
def test_routes_use_membership_org_not_jwt_claim(client, isolated_app, wired, method, path, body) -> None:
    """A forged organization_id claim must not change the scope that is used."""
    membership_org = uuid4()
    claimed_org = uuid4()
    isolated_app.state.membership_repository = FakeMembership("owner", membership_org)
    token = user_token(role="owner", organization_id=claimed_org)

    response = send(client, method, path, body, bearer(token))

    assert response.status_code == 200, response.text
    assert wired.organizations, "route did not reach a repository"
    assert set(wired.organizations) == {membership_org}
    assert claimed_org not in wired.organizations


@pytest.mark.parametrize(("method", "path", "body"), USER_ROUTES)
def test_routes_reject_user_without_membership(client, isolated_app, wired, method, path, body) -> None:
    """No membership row means no access, even with owner claims in the token."""
    isolated_app.state.membership_repository = NoMembership()
    token = user_token(role="owner", organization_id=uuid4())

    response = send(client, method, path, body, bearer(token))

    assert response.status_code == 403
    assert wired.organizations == []


def test_job_creation_ignores_client_supplied_organization_and_actor(client, isolated_app, wired) -> None:
    """device_id comes from the body; organization and actor must not."""
    membership_org = uuid4()
    user_id = uuid4()
    isolated_app.state.membership_repository = FakeMembership("administrator", membership_org)
    token = user_token(user_id, role="viewer", organization_id=uuid4())

    response = client.post(
        "/api/v1/jobs",
        json={
            "device_id": str(uuid4()),
            "action_type": "refresh_inventory",
            "idempotency_key": "injection-key-1",
            "confirmed": True,
            # Both of these are attempts to override server-derived context.
            "organization_id": str(uuid4()),
            "created_by": str(uuid4()),
        },
        headers=bearer(token),
    )

    assert response.status_code == 200, response.text
    assert len(wired.job_requests) == 1
    submitted = wired.job_requests[0]
    assert submitted.organization_id == membership_org
    assert submitted.created_by == user_id


def test_enrollment_token_records_authenticated_actor(client, isolated_app, wired) -> None:
    membership_org = uuid4()
    user_id = uuid4()
    isolated_app.state.membership_repository = FakeMembership("owner", membership_org)

    response = client.post(
        "/api/v1/enrollment-tokens",
        json={"label": "probe", "ttl_minutes": 15},
        headers=bearer(user_token(user_id, role="viewer")),
    )

    assert response.status_code == 200, response.text
    assert wired.organizations == [membership_org]
    assert wired.token_actors == [user_id]


# --------------------------------------------------------------------------- #
# Role gates
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ONLY_ROUTES)
def test_viewer_cannot_reach_admin_routes(client, isolated_app, wired, method, path, body) -> None:
    isolated_app.state.membership_repository = FakeMembership("viewer", uuid4())
    response = send(client, method, path, body, bearer(user_token(role="viewer")))
    assert response.status_code == 403
    assert wired.organizations == []


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ONLY_ROUTES)
def test_owner_claim_does_not_override_viewer_membership(client, isolated_app, wired, method, path, body) -> None:
    """The database role wins over the token's role claim."""
    isolated_app.state.membership_repository = FakeMembership("viewer", uuid4())
    response = send(client, method, path, body, bearer(user_token(role="owner")))
    assert response.status_code == 403
    assert wired.organizations == []


@pytest.mark.parametrize("role", ["owner", "administrator"])
@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ONLY_ROUTES)
def test_privileged_roles_are_allowed_on_admin_routes(
    client, isolated_app, wired, role, method, path, body
) -> None:
    isolated_app.state.membership_repository = FakeMembership(role, uuid4())
    response = send(client, method, path, body, bearer(user_token(role="viewer")))
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(("method", "path", "body"), USER_ROUTES)
def test_viewer_can_read_but_not_write(client, isolated_app, wired, method, path, body) -> None:
    isolated_app.state.membership_repository = FakeMembership("viewer", uuid4())
    response = send(client, method, path, body, bearer(user_token(role="viewer")))
    assert response.status_code == (200 if method == "GET" else 403)


# --------------------------------------------------------------------------- #
# Device credential boundary
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("method", "path", "body"), DEVICE_ROUTES)
def test_device_routes_reject_missing_credential(client, wired, method, path, body) -> None:
    response = send(client, method, path, body, headers={})
    assert response.status_code == 401
    assert response.json()["detail"] == "device_credential_required"


@pytest.mark.parametrize(("method", "path", "body"), DEVICE_ROUTES)
def test_device_routes_reject_human_bearer_token(client, isolated_app, wired, method, path, body) -> None:
    """A valid Supabase session must not authenticate as a device."""
    isolated_app.state.membership_repository = FakeMembership("owner", uuid4())
    response = send(client, method, path, body, bearer(user_token(role="owner")))
    assert response.status_code == 401
    assert response.json()["detail"] == "device_credential_required"


@pytest.mark.parametrize(("method", "path", "body"), DEVICE_ROUTES)
@pytest.mark.parametrize("header", ["Device", "Device ", "device", "Basic abc", "abc"])
def test_device_routes_reject_malformed_credential_header(
    client, wired, method, path, body, header
) -> None:
    response = send(client, method, path, body, {"Authorization": header})
    assert response.status_code == 401
    assert response.json()["detail"] == "device_credential_required"


@pytest.mark.parametrize(("method", "path", "body"), DEVICE_ROUTES)
def test_device_routes_do_not_require_human_membership(client, isolated_app, method, path, body) -> None:
    """Device auth must not consult the human membership boundary at all."""

    class ExplodingMembership:
        def resolve(self, _user_id):
            raise AssertionError("device routes must not resolve human membership")

    isolated_app.state.membership_repository = ExplodingMembership()
    isolated_app.state.job_repository = None
    isolated_app.state.device_repository = None
    isolated_app.state.inventory_repository = None

    response = send(client, method, path, body, {"Authorization": "Device yorg_device_probe"})
    # 503 because the repositories are unconfigured - which proves the request
    # got past authentication without touching human membership.
    assert response.status_code == 503


# --------------------------------------------------------------------------- #
# Unconfigured backend must fail closed, not open
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("method", "path", "body"), USER_ROUTES)
def test_unconfigured_repository_returns_503_not_success(
    client, isolated_app, method, path, body
) -> None:
    isolated_app.state.membership_repository = FakeMembership("owner", uuid4())
    for slot in ("device_repository", "job_repository", "inventory_repository",
                 "policy_repository", "compliance_repository"):
        setattr(isolated_app.state, slot, None)

    response = send(client, method, path, body, bearer(user_token(role="owner")))
    assert response.status_code == 503
