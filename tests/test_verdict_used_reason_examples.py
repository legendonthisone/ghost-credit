"""Example tests: the verdict engine shows the already-used reason."""

from __future__ import annotations

from ghost_credit.paystack import NOT_FOUND, REASON_ALREADY_USED, PaystackResult
from ghost_credit.verdict import decide
from verdict_helpers import make_parsed


def _not_found(reason: str) -> PaystackResult:
    return PaystackResult(NOT_FOUND, True, "ref-1", None, None, reason)


def test_already_used_reason_is_shown() -> None:
    """The exact sentence is the only reason; the code stays NOT_FOUND."""
    v = decide(make_parsed(), _not_found(REASON_ALREADY_USED), None)
    assert v.code == "NOT_FOUND"
    assert v.paystack_checked is True
    assert v.reasons == ["This payment was already used for an earlier check"]
    assert len(v.reasons[0]) <= 120


def test_other_not_found_reason_is_unchanged() -> None:
    """Any other checked NOT_FOUND keeps the usual reason."""
    v = decide(make_parsed(), _not_found("Paystack has no matching payment"), None)
    assert v.code == "NOT_FOUND"
    assert v.reasons == ["Paystack found no matching payment."]
