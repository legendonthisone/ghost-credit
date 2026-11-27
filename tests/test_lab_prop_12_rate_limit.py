"""Property 12: the rate limiter enforces a 20-per-60-second window."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import SlidingWindowLimiter

_gaps = st.lists(st.floats(min_value=0, max_value=30, allow_nan=False), max_size=120)


# Feature: the-lab, Property 12: the limiter enforces a 20-per-60-second window
# **Validates: Requirements 7.5**
@settings(max_examples=100, deadline=None)
@given(_gaps)
def test_limiter_never_allows_more_than_20_in_60_seconds(gaps):
    limiter = SlidingWindowLimiter()
    now = 1000.0
    allowed: list[float] = []
    for gap in gaps:
        now += gap
        if limiter.allow(now):
            allowed.append(now)
    for t in allowed:
        in_window = [a for a in allowed if t - 60 < a <= t]
        assert len(in_window) <= 20


def test_21st_call_in_one_minute_is_denied():
    limiter = SlidingWindowLimiter()
    results = [limiter.allow(1000.0 + i * 0.1) for i in range(21)]
    assert results == [True] * 20 + [False]
    assert limiter.allow(1061.0) is True


# Feature: the-lab, Property 12 (full): the rate limiter enforces its window end to end at the router
# **Validates: Requirements 7.5, 7.6**
@settings(max_examples=100, deadline=None)
@given(_gaps)
def test_router_returns_429_and_skips_check_when_limited(gaps):
    import json
    from datetime import timedelta

    from ghost_credit.lab_router import route
    from lab_fakes import FIXED_NOW, FakeRunCheck

    fake = FakeRunCheck()
    limiter = SlidingWindowLimiter()
    body = json.dumps({"text": "hello"}).encode("utf-8")
    offset = 0.0
    ok_times: list[float] = []
    for gap in gaps:
        offset += gap
        before = len(fake.calls)
        status, _, _ = route(
            "POST", "/lab/check", None, {}, body,
            now=FIXED_NOW + timedelta(seconds=offset), store=None,
            limiter=limiter, run_check_fn=fake,
        )
        if status == 200:
            ok_times.append(offset)
            assert len(fake.calls) == before + 1
        else:
            assert status == 429
            assert len(fake.calls) == before
    for t in ok_times:
        assert len([a for a in ok_times if t - 60 < a <= t]) <= 20
