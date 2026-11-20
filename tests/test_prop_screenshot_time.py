"""Property test: alert time keeps the written clock time."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from hypothesis import assume, given, settings, strategies as st

from ghost_credit.screenshot import build_alert_from_response

PHASH = "phash:0123456789abcdef"


def _time_of(value: str) -> object:
    """Run a string through the validator as alert_time and return the result."""
    return build_alert_from_response(json.dumps({"alert_time": value}), PHASH).alert_time


# Feature: screenshot-reader, Property 4: Alert time keeps the written clock time
@settings(max_examples=150, deadline=None)
@given(
    moment=st.datetimes(
        min_value=datetime(2000, 1, 1), max_value=datetime(2099, 12, 31)
    ),
    offset_minutes=st.integers(-23 * 60 - 59, 23 * 60 + 59),
    with_offset=st.booleans(),
)
def test_prop_alert_time_clock_time(
    moment: datetime, offset_minutes: int, with_offset: bool
) -> None:
    """**Validates: Requirements 5.8, 5.9**"""
    if with_offset:
        moment = moment.replace(tzinfo=timezone(timedelta(minutes=offset_minutes)))
    result = _time_of(moment.isoformat())
    assert result == moment.replace(tzinfo=None)
    assert result.tzinfo is None


@settings(max_examples=150, deadline=None)
@given(text=st.text(max_size=40))
def test_prop_alert_time_rejected_is_none(text: str) -> None:
    """**Validates: Requirements 5.8**"""
    try:
        datetime.fromisoformat(text)
    except (ValueError, TypeError):
        assert _time_of(text) is None
    else:
        assume(False)
