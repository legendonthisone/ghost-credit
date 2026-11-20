"""Property test for the Paystack search window."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import _iso, _search_window

LAGOS = timezone(timedelta(hours=1))

naive = st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1))
zones = st.sampled_from([
    timezone.utc, LAGOS, timezone(timedelta(hours=-5)), timezone(timedelta(hours=5, minutes=30)),
])
aware = st.builds(lambda d, z: d.replace(tzinfo=z), naive, zones)
any_dt = st.one_of(naive, aware)


# Feature: paystack-verifier, Property 8: Search window
# **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 9.2**
@settings(max_examples=200)
@given(alert=st.one_of(st.none(), any_dt), now=any_dt)
def test_window_is_lagos_and_correct_size(alert, now):
    start, end = _search_window(alert, now)
    base = alert if alert is not None else now
    base_lagos = base.replace(tzinfo=LAGOS) if base.tzinfo is None else base.astimezone(LAGOS)
    if alert is not None:
        assert start == base_lagos - timedelta(minutes=30)
        assert end == base_lagos + timedelta(minutes=5)
    else:
        assert start == base_lagos - timedelta(minutes=60)
        assert end == base_lagos
    assert _iso(start).endswith("+01:00")
    assert _iso(end).endswith("+01:00")


# Feature: paystack-verifier, Property 8: Search window (naive equals +01:00)
# **Validates: Requirements 5.4, 5.5**
@settings(max_examples=100)
@given(d=naive)
def test_naive_matches_same_wall_clock_with_offset(d):
    assert _iso(d) == _iso(d.replace(tzinfo=LAGOS))
