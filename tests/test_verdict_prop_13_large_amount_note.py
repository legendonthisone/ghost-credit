"""Feature: verdict-engine, Property 13: Large amount note follows an integer threshold."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import ParsedAlert
from ghost_credit.verdict import risk_notes

NOTE = "Large amount. Take extra care before releasing goods."
DEFAULT = 50000000

_ints = st.integers(min_value=0, max_value=10**11)
_anything = st.one_of(
    _ints, st.booleans(), st.none(), st.floats(allow_nan=False), st.text(max_size=5)
)


def _is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


@settings(max_examples=300)
@given(amount=_anything, threshold=_anything)
def test_note_follows_integer_threshold(amount, threshold) -> None:
    """**Validates: Requirements 5.4, 5.8, 5.9, 5.10**"""
    parsed = ParsedAlert(amount_kobo=amount)
    effective = threshold if _is_int(threshold) else DEFAULT
    expected = _is_int(amount) and amount >= effective
    notes = risk_notes(parsed, large_amount_kobo=threshold)
    assert (NOTE in notes) is expected


@settings(max_examples=100)
@given(amount=_ints)
def test_default_threshold_boundary(amount) -> None:
    """**Validates: Requirements 5.4, 5.9**"""
    assert (NOTE in risk_notes(ParsedAlert(amount_kobo=amount))) is (amount >= DEFAULT)
