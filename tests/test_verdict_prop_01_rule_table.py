"""Feature: verdict-engine, Property 1: Verdict code follows the rule table."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import ParsedAlert
from ghost_credit.verdict import decide
from verdict_helpers import (
    is_network_match,
    is_paystack_confirmed,
    is_paystack_no_match,
    lookup_results,
    paystack_inputs,
    red_flag_lists,
)


def _oracle(flags: list, paystack: object, lookup: object) -> str:
    """Independent restatement of the four rules plus the network step."""
    if is_paystack_confirmed(paystack):
        return "CONFIRMED"
    if is_paystack_no_match(paystack):
        return "NOT_FOUND"
    if flags:
        return "SUSPICIOUS"
    if is_network_match(lookup):
        return "SUSPICIOUS"
    return "UNVERIFIED"


@settings(max_examples=200)
@given(flags=red_flag_lists, paystack=paystack_inputs, lookup=lookup_results)
def test_code_follows_rule_table(flags, paystack, lookup) -> None:
    """**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1**"""
    verdict = decide(ParsedAlert(red_flags=flags), paystack, lookup)
    assert verdict.code == _oracle(flags, paystack, lookup)
