from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from .inventory import InventorySnapshot


class RuleKey(StrEnum):
    bitlocker = "bitlocker"
    firewall = "firewall"
    defender = "defender"
    secure_boot = "secure_boot"
    tpm = "tpm"
    automatic_updates = "automatic_updates"
    windows_edition = "windows_edition"


class RuleOutcome(StrEnum):
    passed = "passed"
    failed = "failed"
    # The agent did not report usable evidence for this field, or the field does
    # not apply to the device's platform. Distinct from `failed`: absence of
    # evidence is not evidence of non-compliance, so it must not lower a score
    # and must never trigger remediation.
    unknown = "unknown"


# Placeholder tokens the collectors emit when a value could not be determined.
# The Windows collector currently reports "not_collected" for every security
# field and the macOS receiver reports "not_collected"/"not_applicable", so
# without this every policy would read as a failure and every score as 0%.
UNKNOWN_EVIDENCE = frozenset({"", "not_collected", "not_available", "unknown", "unavailable"})
NOT_APPLICABLE_EVIDENCE = frozenset({"not_applicable", "n/a"})


class PolicyDefinition(BaseModel):
    policy_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9._-]+$")
    name: str = Field(min_length=1, max_length=160)
    rule_type: RuleKey
    expected_value: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    automatic_remediation: bool = False
    weight: int = Field(default=1, ge=1, le=100)


class PolicyCreateRequest(PolicyDefinition):
    """Owner-controlled policy input; remediation remains opt-in."""


class PolicySummary(PolicyDefinition):
    id: UUID
    created_at: datetime
    updated_at: datetime


class RuleResult(BaseModel):
    outcome: RuleOutcome
    reason: str = Field(min_length=1, max_length=500)
    evidence: dict[str, str]

    @property
    def passed(self) -> bool:
        return self.outcome is RuleOutcome.passed


class ComplianceResult(BaseModel):
    policy_key: str
    outcome: RuleOutcome
    reason: str
    evidence: dict[str, str]
    weight: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        """Kept in the serialized payload for existing consumers.

        Note this is False for both `failed` and `unknown`; read `outcome` when
        the difference matters.
        """
        return self.outcome is RuleOutcome.passed


class ComplianceEvaluation(BaseModel):
    evaluation_id: UUID
    device_id: UUID
    # None when no policy produced usable evidence, so the UI can say
    # "not evaluated" instead of implying a measured 0%.
    score: float | None = Field(default=None, ge=0, le=100)
    evaluated_at: datetime
    evidence_hash: str
    results: list[ComplianceResult]
    scored_weight: int = 0
    unknown_weight: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def unknown_count(self) -> int:
        return sum(1 for result in self.results if result.outcome is RuleOutcome.unknown)


class ComplianceRule(Protocol):
    rule_type: RuleKey

    def evaluate(self, policy: PolicyDefinition, snapshot: InventorySnapshot) -> RuleResult: ...


@dataclass(frozen=True)
class FieldRule:
    rule_type: RuleKey

    def evaluate(self, policy: PolicyDefinition, snapshot: InventorySnapshot) -> RuleResult:
        if self.rule_type == RuleKey.windows_edition:
            actual = snapshot.windows.edition if snapshot.windows else "not_available"
        else:
            actual = getattr(snapshot.security, self.rule_type.value)
        evidence = {
            "field": self.rule_type.value,
            "observed": actual,
            "expected": policy.expected_value,
        }
        observed = actual.strip().casefold()

        if observed in NOT_APPLICABLE_EVIDENCE:
            return RuleResult(
                outcome=RuleOutcome.unknown,
                reason=f"{self.rule_type.value} does not apply to this platform; not scored.",
                evidence=evidence,
            )
        if observed in UNKNOWN_EVIDENCE:
            return RuleResult(
                outcome=RuleOutcome.unknown,
                reason=f"The agent did not report {self.rule_type.value}; not scored.",
                evidence=evidence,
            )

        matched = observed == policy.expected_value.strip().casefold()
        return RuleResult(
            outcome=RuleOutcome.passed if matched else RuleOutcome.failed,
            reason=f"Expected {policy.expected_value}; observed {actual}.",
            evidence=evidence,
        )


RULES: dict[RuleKey, FieldRule] = {key: FieldRule(key) for key in RuleKey}


def evidence_hash(results: list[ComplianceResult]) -> str:
    canonical = json.dumps([result.model_dump(mode="json") for result in results], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate_compliance(
    device_id: UUID,
    snapshot: InventorySnapshot,
    policies: list[PolicyDefinition],
    now: datetime | None = None,
) -> ComplianceEvaluation:
    results: list[ComplianceResult] = []
    for policy in policies:
        if not policy.enabled:
            continue
        result = RULES[policy.rule_type].evaluate(policy, snapshot)
        results.append(
            ComplianceResult(
                policy_key=policy.policy_key,
                weight=policy.weight,
                outcome=result.outcome,
                reason=result.reason,
                evidence=result.evidence,
            )
        )

    # Score only over policies that produced real evidence. Counting `unknown`
    # as a failure would report a measured 0% for a device that simply has not
    # reported that field yet.
    scored_weight = sum(r.weight for r in results if r.outcome is not RuleOutcome.unknown)
    unknown_weight = sum(r.weight for r in results if r.outcome is RuleOutcome.unknown)
    passed_weight = sum(r.weight for r in results if r.outcome is RuleOutcome.passed)
    score = None if scored_weight == 0 else round((passed_weight / scored_weight) * 100, 2)

    return ComplianceEvaluation(
        evaluation_id=uuid4(),
        device_id=device_id,
        score=score,
        evaluated_at=now or datetime.now(UTC),
        evidence_hash=evidence_hash(results),
        results=results,
        scored_weight=scored_weight,
        unknown_weight=unknown_weight,
    )


class RemediationGuard:
    def __init__(self, cooldown: timedelta = timedelta(hours=24)):
        self.cooldown = cooldown
        self.attempts: dict[tuple[UUID, str, str], datetime] = {}

    def should_submit(
        self,
        device_id: UUID,
        policy: PolicyDefinition,
        evidence: ComplianceResult,
        now: datetime | None = None,
    ) -> bool:
        # Remediate only on a measured failure. The previous `not evidence.passed`
        # test also fired for `unknown`, so a policy with automatic_remediation
        # enabled would have submitted a privileged remediation job against a
        # device that had merely failed to report the field.
        if not policy.automatic_remediation or evidence.outcome is not RuleOutcome.failed:
            return False
        current = now or datetime.now(UTC)
        key = (device_id, policy.policy_key, hashlib.sha256(json.dumps(evidence.evidence, sort_keys=True).encode()).hexdigest())
        previous = self.attempts.get(key)
        if previous and current - previous < self.cooldown:
            return False
        self.attempts[key] = current
        return True


class PolicyRepositoryError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class PolicyRepository:
    """Tenant-scoped policy persistence adapter for the existing Supabase schema."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    @staticmethod
    def _summary(row) -> PolicySummary:
        configuration = row[5] or {}
        return PolicySummary(
            id=row[0],
            policy_key=row[2],
            name=row[3],
            rule_type=RuleKey(row[4]),
            expected_value=str(configuration.get("expected_value", "")),
            enabled=row[6],
            automatic_remediation=row[7],
            weight=row[8],
            created_at=row[9],
            updated_at=row[10],
        )

    def list_for_organization(self, organization_id: UUID) -> list[PolicySummary]:
        import psycopg

        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                """
                select id, organization_id, policy_key, name, rule_type, configuration,
                       enabled, automatic_remediation, weight, created_at, updated_at
                from public.compliance_policies
                where organization_id = %s
                order by name asc
                """,
                (organization_id,),
            ).fetchall()
        return [self._summary(row) for row in rows]

    def create(self, organization_id: UUID, request: PolicyCreateRequest) -> PolicySummary:
        import psycopg
        from psycopg.types.json import Jsonb

        try:
            with psycopg.connect(self.database_url) as connection:
                with connection.transaction():
                    row = connection.execute(
                        """
                        insert into public.compliance_policies
                          (organization_id, policy_key, name, rule_type, configuration,
                           enabled, automatic_remediation, weight)
                        values (%s, %s, %s, %s, %s, %s, %s, %s)
                        returning id, organization_id, policy_key, name, rule_type, configuration,
                                  enabled, automatic_remediation, weight, created_at, updated_at
                        """,
                        (
                            organization_id,
                            request.policy_key,
                            request.name,
                            request.rule_type.value,
                            Jsonb({"expected_value": request.expected_value}),
                            request.enabled,
                            request.automatic_remediation,
                            request.weight,
                        ),
                    ).fetchone()
                    if row is None:
                        raise PolicyRepositoryError("policy_create_failed")
                    return self._summary(row)
        except PolicyRepositoryError:
            raise
        except psycopg.errors.UniqueViolation as exc:
            raise PolicyRepositoryError("policy_conflict") from exc


class ComplianceRepository:
    """Read-only evaluation adapter over the current policy and inventory rows."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    def latest_for_organization(self, organization_id: UUID) -> list[ComplianceEvaluation]:
        import psycopg

        policies = [
            PolicyDefinition(**policy.model_dump(exclude={"id", "created_at", "updated_at"}))
            for policy in PolicyRepository(self.database_url).list_for_organization(organization_id)
        ]
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                """
                select distinct on (device_id) device_id, payload
                from public.inventory_snapshots
                where organization_id = %s
                order by device_id, captured_at desc, created_at desc
                """,
                (organization_id,),
            ).fetchall()
        evaluations: list[ComplianceEvaluation] = []
        for device_id, payload in rows:
            snapshot = InventorySnapshot.model_validate(payload)
            evaluations.append(evaluate_compliance(device_id, snapshot, policies))
        return evaluations
