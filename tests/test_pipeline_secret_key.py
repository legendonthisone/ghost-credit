"""The Paystack secret key must never show up in results, logs or errors."""

from __future__ import annotations

import logging
from datetime import datetime

import pytest

from ghost_credit.pipeline import make_paystack_verify, run_check
from pipeline_fakes import RecordingNetwork, RecordingReader, SAMPLE_SMS, alert_with_amount, fake_key

NOW = datetime(2026, 11, 20, 10, 5)


class BrokenHttp:
    """A fake http function that fails and records what it was sent."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        raise RuntimeError("fake http failure")


def test_key_not_in_result_logs_or_errors(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    """With a fake key set and a failing http call, the key text appears nowhere."""
    key = fake_key("secretcheck")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", key)
    http = BrokenHttp()
    with caplog.at_level(logging.DEBUG):
        result = run_check(
            SAMPLE_SMS, "GTBank", b"image", "spa", NOW,
            reader=RecordingReader(alert_with_amount()),
            paystack_verify=make_paystack_verify(http),
            network=RecordingNetwork(),
        )
    assert http.calls >= 1  # the key was really used, and the failure was swallowed
    assert key not in repr(result)
    assert key not in caplog.text
    assert all(key not in str(r.getMessage()) for r in caplog.records)
    assert result.verdict.code != "CONFIRMED"
