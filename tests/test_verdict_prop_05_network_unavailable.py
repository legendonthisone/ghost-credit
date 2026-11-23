"""Feature: verdict-engine, Property 5: An unavailable network equals no network."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import LookupResult
from ghost_credit.verdict import decide
from verdict_helpers import paystack_inputs, parsed_alerts


@settings(max_examples=200)
@given(
    parsed=parsed_alerts,
    paystack=paystack_inputs,
    matched=st.booleans(),
)
def test_unavailable_network_same_as_none(parsed, paystack, matched) -> None:
    """**Validates: Requirements 2.5**"""
    lookup = LookupResult(network_available=False, matched=matched)
    assert decide(parsed, paystack, lookup) == decide(parsed, paystack, None)
