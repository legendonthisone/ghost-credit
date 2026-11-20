"""Example tests for the exact request that verify sends."""

from __future__ import annotations

from datetime import datetime

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)


def test_reference_request_url_and_header() -> None:
    fake = RecordingHttp()
    key = fake_key("abc123")
    verify(make_parsed(claimed_reference="GC/ref 1"), key, NOW, http=fake)
    assert fake.calls == [(
        "https://api.paystack.co/transaction/verify/GC%2Fref%201",
        {"Authorization": "Bearer " + key},
        5.0,
    )]


def test_search_request_url_and_header() -> None:
    fake = RecordingHttp()
    key = fake_key("abc123")
    alert_time = datetime(2026, 11, 20, 10, 2, 11)
    verify(make_parsed(alert_time=alert_time), key, NOW, http=fake)
    assert fake.calls == [(
        "https://api.paystack.co/transaction?status=success"
        "&from=2026-11-20T09%3A32%3A11%2B01%3A00"
        "&to=2026-11-20T10%3A07%3A11%2B01%3A00&perPage=100",
        {"Authorization": "Bearer " + key},
        5.0,
    )]


def test_search_without_alert_time_uses_last_hour_from_now() -> None:
    fake = RecordingHttp()
    verify(make_parsed(), fake_key("abc123"), NOW, http=fake)
    url = fake.calls[0][0]
    assert "from=2026-11-20T09%3A05%3A00%2B01%3A00" in url
    assert "to=2026-11-20T10%3A05%3A00%2B01%3A00" in url
