"""Feature: verdict-engine, Property 3: Only Paystack can confirm."""

from __future__ import annotations

from hypothesis import given, settings

from ghost_credit.verdict import decide
from verdict_helpers import lookup_results, not_confirmed_results, parsed_alerts


@settings(max_examples=200)
@given(parsed=parsed_alerts, paystack=not_confirmed_results, lookup=lookup_results)
def test_never_confirmed_without_paystack(parsed, paystack, lookup) -> None:
    """**Validates: Requirements 2.4, 8.1**"""
    assert decide(parsed, paystack, lookup).code != "CONFIRMED"
