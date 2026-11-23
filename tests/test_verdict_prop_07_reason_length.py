"""Feature: verdict-engine, Property 7: Every reason is 1 to 120 characters."""

from __future__ import annotations

from hypothesis import given, settings

from ghost_credit.parser import ParsedAlert
from ghost_credit.verdict import decide
from verdict_helpers import lookup_results, paystack_inputs, red_flag_lists


@settings(max_examples=200)
@given(flags=red_flag_lists, paystack=paystack_inputs, lookup=lookup_results)
def test_reasons_are_short_and_not_empty(flags, paystack, lookup) -> None:
    """**Validates: Requirements 3.4, 3.5, 8.6**"""
    reasons = decide(ParsedAlert(red_flags=flags), paystack, lookup).reasons
    assert reasons
    assert all(isinstance(r, str) and 1 <= len(r) <= 120 for r in reasons)
