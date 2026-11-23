"""Feature: verdict-engine, Property 19: Replies for unconfirmed verdicts end with the reminder."""

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
    FakeExplainer,
    TemplateExplainer,
    build_reply,
)


class _Text(Explainer):
    """Returns the given text unchanged."""

    def __init__(self, text: str) -> None:
        self.text = text

    def explain(self, verdict, parsed, risk_notes):  # type: ignore[no-untyped-def]
        return self.text


codes = st.sampled_from([NOT_FOUND, SUSPICIOUS, UNVERIFIED])
verdicts = st.builds(
    lambda code, reasons: Verdict(code=code, paystack_checked=False, reasons=reasons),
    codes,
    st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=4),
)
texts = st.one_of(
    st.text(max_size=60),
    st.text(max_size=30).map(lambda t: t + CHECK_REMINDER),
    st.text(max_size=30).map(lambda t: t + CHECK_REMINDER + "  \n"),
)
notes_st = st.lists(
    st.text(alphabet="abcdefgh .,", min_size=1, max_size=30).map(str.strip).filter(bool),
    max_size=3,
)


@settings(max_examples=100)
@given(verdict=verdicts, text=texts, notes=notes_st)
def test_arbitrary_text_ends_with_reminder_once(verdict, text, notes) -> None:
    """**Validates: Requirements 7.1, 7.2, 7.3, 8.10**"""
    reply = build_reply(verdict, None, _Text(text), notes)
    assert reply.endswith(CHECK_REMINDER)
    if text.rstrip().endswith(CHECK_REMINDER) and text.strip():
        assert reply == text.rstrip()
    else:
        assert reply.count(CHECK_REMINDER) == reply.rstrip().count(CHECK_REMINDER)


@settings(max_examples=100)
@given(verdict=verdicts, notes=notes_st, which=st.sampled_from([TemplateExplainer, FakeExplainer]))
def test_notes_sit_before_reminder(verdict, notes, which) -> None:
    """**Validates: Requirements 7.1, 7.2, 7.3, 7.5**"""
    reply = build_reply(verdict, None, which(), notes)
    assert reply.endswith(CHECK_REMINDER)
    assert reply.count(CHECK_REMINDER) == 1
    cut = reply.rindex(CHECK_REMINDER)
    for note in notes:
        assert note in reply[:cut]


@settings(max_examples=100)
@given(text=st.text(min_size=1, max_size=60).filter(lambda t: t.strip()))
def test_confirmed_text_is_unchanged(text) -> None:
    """**Validates: Requirements 7.4**"""
    verdict = Verdict(code=CONFIRMED, paystack_checked=True, reasons=["ok"])
    assert build_reply(verdict, None, _Text(text), []) == text
