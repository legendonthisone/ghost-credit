"""Feature: verdict-engine, Property 11: Notes never change the verdict or the red flags."""

from __future__ import annotations

import copy

from hypothesis import given, settings, strategies as st

from ghost_credit.verdict import decide, decide_with_notes
from verdict_helpers import lookup_results, paystack_inputs, parsed_alerts


@settings(max_examples=100)
@given(
    parsed=parsed_alerts,
    paystack=paystack_inputs,
    lookup=lookup_results,
    text=st.one_of(st.none(), st.text(max_size=40), st.just("A rider is here")),
    threshold=st.one_of(st.integers(0, 10**11), st.none(), st.floats(), st.booleans()),
)
def test_decision_verdict_equals_decide(parsed, paystack, lookup, text, threshold) -> None:
    """**Validates: Requirements 5.1, 5.2, 8.4**"""
    flags_before = copy.deepcopy(parsed.red_flags)
    decision = decide_with_notes(
        parsed, paystack, lookup, alert_text=text, large_amount_kobo=threshold  # type: ignore[arg-type]
    )
    assert decision.verdict == decide(parsed, paystack, lookup)
    assert parsed.red_flags == flags_before
