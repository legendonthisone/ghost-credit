"""Feature: verdict-engine, Property 15: The note list is ordered, unique and safe."""

from __future__ import annotations

import copy
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import ParsedAlert
from ghost_credit.verdict import risk_notes

ORDER = [
    "Sent late on a Friday or at the weekend, a common time for fake alerts.",
    "Large amount. Take extra care before releasing goods.",
    "Someone is coming to collect at once. "
    "Do not release goods until the money shows in your bank app.",
]


class _Raises:
    """A parsed-alert stand-in whose attributes cannot be read."""

    def __getattr__(self, name: str) -> object:
        raise RuntimeError("boom")


@settings(max_examples=200)
@given(
    when=st.one_of(st.none(), st.datetimes(min_value=datetime(2000, 1, 5),
                                           max_value=datetime(2090, 1, 1))),
    amount=st.one_of(st.none(), st.integers(min_value=0, max_value=10**11)),
    text=st.one_of(st.none(), st.text(max_size=30),
                   st.sampled_from(["driver here", "Pick up now"])),
    threshold=st.one_of(st.integers(min_value=0, max_value=10**11), st.none()),
)
def test_notes_are_an_ordered_unique_subsequence(when, amount, text, threshold) -> None:
    """**Validates: Requirements 5.11, 5.13**"""
    parsed = ParsedAlert(alert_time=when, amount_kobo=amount, red_flags=["DATE_ODD"])
    before = copy.deepcopy(parsed)
    notes = risk_notes(parsed, alert_text=text, large_amount_kobo=threshold)  # type: ignore[arg-type]
    assert len(notes) == len(set(notes))
    positions = [ORDER.index(n) for n in notes]
    assert positions == sorted(positions)
    assert parsed == before


def test_nothing_applies_gives_empty_list() -> None:
    """**Validates: Requirements 5.11**"""
    assert risk_notes(ParsedAlert()) == []


def test_forced_error_gives_empty_list() -> None:
    """**Validates: Requirements 5.12**"""
    assert risk_notes(_Raises(), alert_text="rider") == []  # type: ignore[arg-type]
