"""Feature: verdict-engine, Property 8: Reasons explain the verdict and hold no notes."""

from __future__ import annotations

from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import ParsedAlert
from ghost_credit.paystack import REASON_ALREADY_USED
from ghost_credit.verdict import FLAG_REASONS, decide, risk_notes
from verdict_helpers import (
    KNOWN_FLAGS,
    is_network_match,
    lookup_results,
    paystack_inputs,
    red_flag_lists,
)

_GENERIC = "Something else about this alert looks wrong."


@settings(max_examples=200)
@given(
    flags=red_flag_lists,
    paystack=paystack_inputs,
    lookup=lookup_results,
    amount=st.one_of(st.none(), st.integers(min_value=0, max_value=10**11)),
    when=st.one_of(st.none(), st.datetimes(min_value=datetime(2000, 1, 2),
                                           max_value=datetime(2090, 1, 1))),
    text=st.sampled_from(["", "rider is outside", "pick up now please"]),
)
def test_reasons_match_verdict(flags, paystack, lookup, amount, when, text) -> None:
    """**Validates: Requirements 3.6, 3.7, 3.8, 3.9, 3.10, 3.11**"""
    parsed = ParsedAlert(red_flags=flags, amount_kobo=amount, alert_time=when)
    v = decide(parsed, paystack, lookup)
    if v.code == "CONFIRMED":
        assert v.reasons == ["Paystack found a matching payment."]
    elif v.code == "NOT_FOUND":
        if paystack.reason == REASON_ALREADY_USED:
            assert v.reasons == [REASON_ALREADY_USED]
        else:
            assert v.reasons == ["Paystack found no matching payment."]
    elif flags:
        expected = [
            FLAG_REASONS[f] if isinstance(f, str) and f in FLAG_REASONS else _GENERIC
            for f in flags
        ]
        assert v.reasons == expected
        for reason in v.reasons:
            assert not any(code in reason for code in KNOWN_FLAGS)
    elif is_network_match(lookup):
        assert v.reasons == ["The pattern network has seen a similar alert."]
    else:
        assert v.code == "UNVERIFIED"
        assert v.reasons == ["No Paystack check was possible and no red flags were found."]
    for note in risk_notes(parsed, alert_text=text):
        assert note not in v.reasons
