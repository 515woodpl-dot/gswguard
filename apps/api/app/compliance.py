from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .inventory import InventorySnapshot


class RuleKey(StrEnum):
    bitlocker = "bitlocker"
    firewall = "firewall"
    defender = "defender"
    secure_boot = "secure_boot"
    tpm = "tpm"
    automatic_updates = "automatic_updates"
    windows_edition = "windows_edition"


class PolicyDefinition(BaseModel):
    policy_key: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    rule_type: RuleKey
    expected_value: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    automatic_remediation: bool = False
    weight: int = Field(default=1, ge=1, le=100)


class RuleResult(BaseModel):
    passed: bool
    reason: str = Field(min_length=1, max_length=500)
    evidence: dict[str, str]


class ComplianceResult(BaseModel):
    policy_key: str
    passed: bool
    reason: str
    evidence: dict[str, str]
    weight: int


class ComplianceEvaluation(BaseModel):
    evaluation_id: UUID
    device_id: UUID
    score: float = Field(ge=0, le=100)
    evaluated_at: datetime
    evidence_hash: str
    results: list[ComplianceResult]


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
        passed = actual.casefold() == policy.expected_value.casefold()
        return RuleResult(
            passed=passed,
            reason=f"Expected {policy.expected_value}; observed {actual}.",
            evidence={"field": self.rule_type.value, "observed": actual, "expected": policy.expected_value},
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
        results.append(ComplianceResult(policy_key=policy.policy_key, weight=policy.weight, **result.model_dump()))
    total_weight = sum(result.weight for result in results)
    passed_weight = sum(result.weight for result in results if result.passed)
    score = 100.0 if total_weight == 0 else round((passed_weight / total_weight) * 100, 2)
    evaluated_at = now or datetime.now(UTC)
    return ComplianceEvaluation(
        evaluation_id=uuid4(),
        device_id=device_id,
        score=score,
        evaluated_at=evaluated_at,
        evidence_hash=evidence_hash(results),
        results=results,
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
        if not policy.automatic_remediation or evidence.passed:
            return False
        current = now or datetime.now(UTC)
        key = (device_id, policy.policy_key, hashlib.sha256(json.dumps(evidence.evidence, sort_keys=True).encode()).hexdigest())
        previous = self.attempts.get(key)
        if previous and current - previous < self.cooldown:
            return False
        self.attempts[key] = current
        return True
