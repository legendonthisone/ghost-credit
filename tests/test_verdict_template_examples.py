"""Example tests for TemplateExplainer (fixed text, no AI, no network)."""

from __future__ import annotations

import pytest

from ghost_credit.pattern_network import Verdict
from ghost_credit.verdict import (
    CHECK_REMINDER,
    CONFIRMED,
    NOT_FOUND,
    OWNER_LABELS,
    SUSPICIOUS,
    UNVERIFIED,
    TemplateExplainer,
)

NOTE = "Large amount. Take extra care before releasing goods."


def _verdict(code: str, reasons: list[str]) -> Verdict:
    return Verdict(code=code, paystack_checked=code in (CONFIRMED, NOT_FOUND), reasons=reasons)


@pytest.mark.parametrize("code", [CONFIRMED, NOT_FOUND, SUSPICIOUS, UNVERIFIED])
def test_layout_for_each_code(code: str) -> None:
    """**Validates: Requirements 6.3, 6.4, 6.5**"""
    reasons = ["reason one", "reason two", "reason three", "reason four"]
    text = TemplateExplainer().explain(_verdict(code, reasons), None, [NOTE])
    assert text.startswith(OWNER_LABELS[code])
    assert "reason three" in text and "reason four" not in text
    assert text.index("reason three") < text.index(NOTE)
    if code == CONFIRMED:
        assert CHECK_REMINDER not in text
    else:
        assert text.endswith(CHECK_REMINDER)
        assert text.index(NOTE) < text.index(CHECK_REMINDER)


def test_unknown_code_uses_unverified_headline() -> None:
    """**Validates: Requirements 6.3**"""
    v = _verdict(UNVERIFIED, ["x"])
    v.code = "WEIRD"
    text = TemplateExplainer().explain(v, None, [])
    assert text.startswith("UNVERIFIED") and text.endswith(CHECK_REMINDER)
