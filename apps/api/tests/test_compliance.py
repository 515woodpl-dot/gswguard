from datetime import UTC, datetime
from uuid import uuid4

from apps.api.app.compliance import (
    PolicyDefinition,
    RemediationGuard,
    RuleKey,
    evaluate_compliance,
)
from apps.api.tests.test_inventory import snapshot


def test_compliance_evaluation_scores_weighted_results_and_retains_evidence() -> None:
    policies = [
        PolicyDefinition(policy_key="bitlocker-on", name="BitLocker enabled", rule_type=RuleKey.bitlocker, expected_value="on", weight=2),
        PolicyDefinition(policy_key="firewall-on", name="Firewall enabled", rule_type=RuleKey.firewall, expected_value="on", weight=1),
        PolicyDefinition(policy_key="defender-healthy", name="Defender healthy", rule_type=RuleKey.defender, expected_value="healthy", weight=1),
    ]
    result = evaluate_compliance(uuid4(), snapshot(), policies)
    assert result.score == 100
    assert len(result.results) == 3
    assert result.evidence_hash


def test_failed_policy_lowers_score_and_auto_remediation_requires_explicit_enablement() -> None:
    policy = PolicyDefinition(policy_key="defender-healthy", name="Defender healthy", rule_type=RuleKey.defender, expected_value="healthy", weight=2)
    failing_snapshot = snapshot()
    failing_snapshot.security.defender = "unhealthy"
    result = evaluate_compliance(uuid4(), failing_snapshot, [policy])
    assert result.score == 0
    guard = RemediationGuard()
    assert not guard.should_submit(uuid4(), policy, result.results[0])
    policy.automatic_remediation = True
    device_id = uuid4()
    now = datetime(2026, 7, 24, tzinfo=UTC)
    assert guard.should_submit(device_id, policy, result.results[0], now)
    assert not guard.should_submit(device_id, policy, result.results[0], now)
