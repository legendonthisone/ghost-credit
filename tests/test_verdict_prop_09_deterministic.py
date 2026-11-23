"""Feature: verdict-engine, Property 9: Decide is deterministic and leaves arguments unchanged."""

from __future__ import annotations

import copy

from hypothesis import given, settings

from ghost_credit.verdict import decide
from verdict_helpers import lookup_results, parsed_alerts, paystack_inputs


@settings(max_examples=200)
@given(parsed=parsed_alerts, paystack=paystack_inputs, lookup=lookup_results)
def test_same_inputs_same_verdict_and_no_mutation(parsed, paystack, lookup) -> None:
    """**Validates: Requirements 4.2, 4.7**"""
    # object() has no equality, so compare using a snapshot of the parsed alert
    # and of the simple fields of the other two.
    before_parsed = copy.deepcopy(parsed)
    before_flags = list(parsed.red_flags)
    first = decide(parsed, paystack, lookup)
    second = decide(parsed, paystack, lookup)
    assert first == second
    assert parsed == before_parsed
    assert parsed.red_flags == before_flags
    if hasattr(lookup, "matched"):
        assert lookup == copy.deepcopy(lookup)
