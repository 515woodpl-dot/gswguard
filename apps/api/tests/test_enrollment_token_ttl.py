"""Locks in the tightened enrollment-token TTL bounds.

The token is embedded in a downloadable bootstrap file, so its lifetime is
deliberately short. These tests fail if the bounds are widened back.
"""
import pytest
from pydantic import ValidationError

from apps.api.app.devices import EnrollmentTokenRequest


def test_default_ttl_is_short() -> None:
    assert EnrollmentTokenRequest().ttl_minutes == 15


def test_ttl_cannot_exceed_one_hour() -> None:
    with pytest.raises(ValidationError):
        EnrollmentTokenRequest(ttl_minutes=61)


def test_ttl_has_a_floor() -> None:
    with pytest.raises(ValidationError):
        EnrollmentTokenRequest(ttl_minutes=4)


def test_ttl_accepts_values_in_range() -> None:
    assert EnrollmentTokenRequest(ttl_minutes=60).ttl_minutes == 60
    assert EnrollmentTokenRequest(ttl_minutes=5).ttl_minutes == 5
