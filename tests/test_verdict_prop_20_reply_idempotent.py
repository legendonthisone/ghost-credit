"""Feature: verdict-engine, Property 20: Reply building is idempotent."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import Verdict
from ghost_credit.verdict import (
    CHECK_REMINDER,
    CONFIRMED,
    NOT_FOUND,
    SUSPICIOUS,
    UNVERIFIED,
    Explainer,
    build_reply,
)


class _Text(Explainer):
    """Returns the given text unchanged."""

    def __init__(self, text: str) -> None:
        self.text = text

    def explain(self, verdict, parsed, risk_notes):  # type: ignore[no-untyped-def]
        return self.text


@settings(max_examples=100)
@given(
    code=st.sampled_from([CONFIRMED, NOT_FOUND, SUSPICIOUS, UNVERIFIED]),
    text=st.one_of(st.text(max_size=60),
                   st.text(max_size=30).map(lambda t: t + CHECK_REMINDER + " \n")),
    notes=st.lists(st.text(min_size=1, max_size=30), max_size=3),
    reasons=st.lists(st.text(min_size=1, max_size=30), max_size=3),
)
def test_second_pass_gives_same_reply(code, text, notes, reasons) -> None:
    """**Validates: Requirements 7.6**"""
    verdict = Verdict(code=code, paystack_checked=False, reasons=reasons)
    first = build_reply(verdict, None, _Text(text), notes)
    second = build_reply(verdict, None, _Text(first), notes)
    assert second == first
