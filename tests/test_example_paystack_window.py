"""Example tests for the Paystack search window with naive and aware times."""

from __future__ import annotations

from datetime import datetime, timezone

from ghost_credit.paystack import _iso, _search_window

NOW = datetime(2026, 11, 20, 12, 0, 0)


def _texts(alert):
    start, end = _search_window(alert, NOW)
    return _iso(start), _iso(end)


def test_naive_alert_time_is_lagos():
    assert _texts(datetime(2026, 11, 20, 10, 2, 11)) == (
        "2026-11-20T09:32:11+01:00",
        "2026-11-20T10:07:11+01:00",
    )


def test_aware_utc_alert_time_is_converted_to_lagos():
    alert = datetime(2026, 11, 20, 9, 2, 11, tzinfo=timezone.utc)  # 10:02:11 Lagos
    assert _texts(alert) == (
        "2026-11-20T09:32:11+01:00",
        "2026-11-20T10:07:11+01:00",
    )


def test_no_alert_time_uses_last_hour_to_now():
    assert _texts(None) == ("2026-11-20T11:00:00+01:00", "2026-11-20T12:00:00+01:00")
