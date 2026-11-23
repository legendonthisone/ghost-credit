"""Example tests for the Safe_Fallback_Result shape."""

from __future__ import annotations

from ghost_credit.parser import ParsedAlert
from ghost_credit.paystack import UNAVAILABLE
from ghost_credit.pipeline import FALLBACK_REASON, _safe_fallback
from ghost_credit.verdict import CHECK_REMINDER


def test_fallback_has_fixed_values() -> None:
    """The fallback is UNVERIFIED, rules-decided, unchecked and reminds the owner."""
    parsed = ParsedAlert(amount_kobo=4500000)
    result = _safe_fallback("abc", parsed)
    assert result.check_id == "abc"
    assert result.parsed is parsed
    assert result.verdict.code == "UNVERIFIED"
    assert result.verdict.decided_by == "rules"
    assert result.verdict.paystack_checked is False
    assert result.verdict.owner_outcome == "unknown"
    assert result.verdict.reasons == [FALLBACK_REASON]
    assert result.reply == FALLBACK_REASON + " " + CHECK_REMINDER
    assert result.paystack_result.status == UNAVAILABLE
    assert result.paystack_result.checked is False
    assert result.risk_notes == []


def test_fallback_calls_return_separate_objects() -> None:
    """Changing one fallback's verdict or reasons must not touch another."""
    first = _safe_fallback("a", ParsedAlert())
    second = _safe_fallback("b", ParsedAlert())
    assert first.verdict is not second.verdict
    assert first.verdict.reasons is not second.verdict.reasons
    first.verdict.reasons.append("changed")
    assert second.verdict.reasons == [FALLBACK_REASON]
