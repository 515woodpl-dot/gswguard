from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.api.app.compliance import (
    PolicyCreateRequest,
    PolicyDefinition,
    RemediationGuard,
    RuleKey,
    RuleOutcome,
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


def test_policy_creation_defaults_to_observation_only() -> None:
    policy = PolicyCreateRequest(
        policy_key="firewall-on",
        name="Firewall enabled",
        rule_type=RuleKey.firewall,
        expected_value="on",
    )

    assert policy.enabled
    assert not policy.automatic_remediation
    assert policy.weight == 1


# --------------------------------------------------------------------------- #
# Missing evidence must not read as non-compliance. Audit finding C3.
#
# Both shipped collectors report placeholder values for the security posture:
# WindowsInventoryCollector.cs hardcodes "not_collected" for all six fields and
# the macOS receiver reports "not_collected"/"not_applicable". Scoring those as
# failures made every device report 0% compliance.
# --------------------------------------------------------------------------- #


def firewall_policy(**overrides) -> PolicyDefinition:
    fields = {
        "policy_key": "firewall-on",
        "name": "Firewall enabled",
        "rule_type": RuleKey.firewall,
        "expected_value": "on",
    }
    fields.update(overrides)
    return PolicyDefinition(**fields)


@pytest.mark.parametrize("placeholder", ["not_collected", "not_available", "unknown", "unavailable"])
def test_uncollected_evidence_is_unknown_not_failed(placeholder: str) -> None:
    uncollected = snapshot()
    uncollected.security.firewall = placeholder

    result = evaluate_compliance(uuid4(), uncollected, [firewall_policy()])

    assert result.results[0].outcome is RuleOutcome.unknown
    assert result.results[0].passed is False
    # The key assertion: no measured score, rather than a measured zero.
    assert result.score is None
    assert result.scored_weight == 0
    assert result.unknown_weight == 1
    assert result.unknown_count == 1


def test_not_applicable_evidence_is_excluded_from_scoring() -> None:
    """BitLocker on a Mac is not a compliance failure."""
    mac = snapshot()
    mac.security.bitlocker = "not_applicable"
    policies = [
        PolicyDefinition(policy_key="bitlocker-on", name="BitLocker", rule_type=RuleKey.bitlocker, expected_value="on", weight=3),
        firewall_policy(weight=1),
    ]

    result = evaluate_compliance(uuid4(), mac, policies)

    outcomes = {r.policy_key: r.outcome for r in result.results}
    assert outcomes["bitlocker-on"] is RuleOutcome.unknown
    assert outcomes["firewall-on"] is RuleOutcome.passed
    # Only the firewall weight is scored, so a passing firewall is still 100%.
    assert result.score == 100
    assert result.scored_weight == 1
    assert result.unknown_weight == 3


def test_partial_evidence_scores_only_what_was_measured() -> None:
    partial = snapshot()
    partial.security.firewall = "off"          # measured failure, weight 1
    partial.security.defender = "not_collected"  # unknown, weight 9
    policies = [
        firewall_policy(weight=1),
        PolicyDefinition(policy_key="defender-healthy", name="Defender", rule_type=RuleKey.defender, expected_value="healthy", weight=9),
    ]

    result = evaluate_compliance(uuid4(), partial, policies)

    # 0% of the *measured* weight passed. The unknown weight does not dilute it
    # in either direction.
    assert result.score == 0
    assert result.scored_weight == 1
    assert result.unknown_weight == 9


def test_real_evidence_still_scores_normally() -> None:
    mixed = snapshot()
    mixed.security.firewall = "off"
    policies = [
        firewall_policy(weight=1),
        PolicyDefinition(policy_key="bitlocker-on", name="BitLocker", rule_type=RuleKey.bitlocker, expected_value="on", weight=3),
    ]

    result = evaluate_compliance(uuid4(), mixed, policies)

    assert result.score == 75
    assert result.unknown_weight == 0


def test_remediation_never_fires_on_missing_evidence() -> None:
    """The dangerous case: automatic remediation driven by absent evidence."""
    policy = firewall_policy(automatic_remediation=True)
    uncollected = snapshot()
    uncollected.security.firewall = "not_collected"

    result = evaluate_compliance(uuid4(), uncollected, [policy])
    guard = RemediationGuard()

    assert result.results[0].outcome is RuleOutcome.unknown
    assert not guard.should_submit(uuid4(), policy, result.results[0])


def test_remediation_still_fires_on_measured_failure() -> None:
    policy = firewall_policy(automatic_remediation=True)
    failing = snapshot()
    failing.security.firewall = "off"

    result = evaluate_compliance(uuid4(), failing, [policy])

    assert result.results[0].outcome is RuleOutcome.failed
    assert RemediationGuard().should_submit(uuid4(), policy, result.results[0])


def test_windows_edition_on_a_non_windows_snapshot_is_unknown() -> None:
    mac = snapshot()
    mac.windows = None
    policy = PolicyDefinition(
        policy_key="edition-pro", name="Edition", rule_type=RuleKey.windows_edition, expected_value="Pro"
    )

    result = evaluate_compliance(uuid4(), mac, [policy])

    assert result.results[0].outcome is RuleOutcome.unknown
    assert result.score is None
