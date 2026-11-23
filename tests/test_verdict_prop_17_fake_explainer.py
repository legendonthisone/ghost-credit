"""Feature: verdict-engine, Property 17: FakeExplainer is deterministic."""

from __future__ import annotations

import copy

from hypothesis import given, settings, strategies as st

from ghost_credit.verdict import FakeExplainer, decide
from verdict_helpers import lookup_results, paystack_inputs, parsed_alerts


@settings(max_examples=100)
@given(
    parsed=parsed_alerts,
    paystack=paystack_inputs,
    lookup=lookup_results,
    notes=st.lists(st.text(max_size=30), max_size=3),
)
def test_fake_explainer_is_deterministic(parsed, paystack, lookup, notes) -> None:
    """**Validates: Requirements 6.7**"""
    verdict = decide(parsed, paystack, lookup)
    v_before, p_before, n_before = (
        copy.deepcopy(verdict), copy.deepcopy(parsed), list(notes),
    )
    first = FakeExplainer().explain(verdict, parsed, notes)
    second = FakeExplainer().explain(copy.deepcopy(verdict), copy.deepcopy(parsed), list(notes))
    assert first == second
    assert (verdict, parsed, notes) == (v_before, p_before, n_before)
