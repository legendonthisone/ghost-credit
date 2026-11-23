"""Feature: verdict-engine, Property 2: A Paystack result beats the network."""

from __future__ import annotations

from hypothesis import given, settings

from ghost_credit.verdict import decide
from verdict_helpers import confirmed_results, lookup_results, no_match_results, parsed_alerts


@settings(max_examples=200)
@given(parsed=parsed_alerts, paystack=confirmed_results, lookup=lookup_results)
def test_confirmed_stays_confirmed(parsed, paystack, lookup) -> None:
    """**Validates: Requirements 2.2, 8.2**"""
    assert decide(parsed, paystack, lookup).code == "CONFIRMED"


@settings(max_examples=200)
@given(parsed=parsed_alerts, paystack=no_match_results, lookup=lookup_results)
def test_no_match_stays_not_found(parsed, paystack, lookup) -> None:
    """**Validates: Requirements 2.3**"""
    assert decide(parsed, paystack, lookup).code == "NOT_FOUND"
