"""Feature: verdict-engine, Property 6: Verdict fields are fixed by the rules."""

from __future__ import annotations

from hypothesis import given, settings

from ghost_credit.verdict import decide
from verdict_helpers import (
    is_paystack_confirmed,
    is_paystack_no_match,
    lookup_results,
    parsed_alerts,
    paystack_inputs,
)


@settings(max_examples=200)
@given(parsed=parsed_alerts, paystack=paystack_inputs, lookup=lookup_results)
def test_fixed_fields(parsed, paystack, lookup) -> None:
    """**Validates: Requirements 3.1, 3.2, 3.3**"""
    v = decide(parsed, paystack, lookup)
    assert v.decided_by == "rules"
    assert v.owner_outcome == "unknown"
    expected = is_paystack_confirmed(paystack) or is_paystack_no_match(paystack)
    assert v.paystack_checked is expected
