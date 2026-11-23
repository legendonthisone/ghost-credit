"""Feature: verdict-engine, Property 12: Friday and weekend note follows Lagos time."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import ParsedAlert
from ghost_credit.verdict import risk_notes

NOTE = "Sent late on a Friday or at the weekend, a common time for fake alerts."

_offsets = st.one_of(
    st.none(),
    st.integers(min_value=-12 * 60, max_value=14 * 60).map(
        lambda m: timezone(timedelta(minutes=m))
    ),
)
_times = st.builds(
    lambda naive, tz: naive.replace(tzinfo=tz),
    st.datetimes(min_value=datetime(2000, 1, 5), max_value=datetime(2090, 1, 1)),
    _offsets,
)


def _expected(moment: datetime) -> bool:
    """Oracle: shift to UTC by hand, add one hour, then read weekday and hour."""
    offset = moment.utcoffset()
    if offset is None:
        lagos = moment.replace(tzinfo=None)  # naive already means Lagos
    else:
        lagos = moment.replace(tzinfo=None) - offset + timedelta(hours=1)
    return (lagos.weekday() == 4 and lagos.hour >= 14) or lagos.weekday() in (5, 6)


@settings(max_examples=300)
@given(moment=_times)
def test_note_matches_lagos_time(moment) -> None:
    """**Validates: Requirements 5.3**"""
    notes = risk_notes(ParsedAlert(alert_time=moment))
    assert (NOTE in notes) is _expected(moment)


@settings(max_examples=100)
@given(value=st.one_of(st.none(), st.integers(), st.text(max_size=10),
                       st.dates()))
def test_no_time_no_note(value) -> None:
    """**Validates: Requirements 5.10**"""
    assert NOTE not in risk_notes(ParsedAlert(alert_time=value))  # type: ignore[arg-type]
