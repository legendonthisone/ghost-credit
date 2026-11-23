"""Examples: each verdict rule, the network step and the internal-error fallback."""

from __future__ import annotations

from ghost_credit.pattern_network import LookupResult
from ghost_credit.verdict import decide
from verdict_helpers import make_parsed, make_paystack

NO_NETWORK = LookupResult(network_available=False, matched=False)
MATCH = LookupResult(network_available=True, matched=True)


def test_rule_1_paystack_match_is_confirmed() -> None:
    v = decide(make_parsed(), make_paystack("CONFIRMED"), NO_NETWORK)
    assert v.code == "CONFIRMED"
    assert v.paystack_checked is True
    assert v.reasons == ["Paystack found a matching payment."]


def test_rule_2_paystack_no_match_is_not_found() -> None:
    v = decide(make_parsed(), make_paystack("NOT_FOUND", True), NO_NETWORK)
    assert v.code == "NOT_FOUND"
    assert v.paystack_checked is True


def test_rule_3_red_flags_without_paystack_is_suspicious() -> None:
    parsed = make_parsed(red_flags=["SENDER_ID_MISMATCH", "DATE_ODD"])
    v = decide(parsed, None, NO_NETWORK)
    assert v.code == "SUSPICIOUS"
    assert v.paystack_checked is False
    assert len(v.reasons) == 2
    assert not any("SENDER_ID" in r or "DATE_ODD" in r for r in v.reasons)


def test_rule_4_nothing_to_go_on_is_unverified() -> None:
    v = decide(make_parsed(), make_paystack("UNAVAILABLE", False), NO_NETWORK)
    assert v.code == "UNVERIFIED"
    assert v.decided_by == "rules"
    assert v.owner_outcome == "unknown"


def test_network_match_turns_unverified_into_suspicious() -> None:
    v = decide(make_parsed(), None, MATCH)
    assert v.code == "SUSPICIOUS"
    assert v.reasons == ["The pattern network has seen a similar alert."]


def test_network_match_cannot_change_a_paystack_result() -> None:
    assert decide(make_parsed(), make_paystack("CONFIRMED"), MATCH).code == "CONFIRMED"
    assert decide(make_parsed(), make_paystack("NOT_FOUND", True), MATCH).code == "NOT_FOUND"


def test_unknown_flag_counts_and_gets_generic_reason() -> None:
    v = decide(make_parsed(red_flags=["X" * 500]), None, None)
    assert v.code == "SUSPICIOUS"
    assert all(1 <= len(r) <= 120 for r in v.reasons)


def test_fallback_when_red_flags_raise_on_copy() -> None:
    class Exploding(list):
        def __iter__(self):
            raise RuntimeError("boom")

    v = decide(make_parsed(red_flags=Exploding(["DATE_ODD"])), None, None)
    assert v.code == "UNVERIFIED"
    assert v.decided_by == "rules"
    assert v.reasons == ["The check could not be completed."]
