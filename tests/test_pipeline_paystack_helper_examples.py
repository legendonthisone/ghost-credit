"""Example tests for make_paystack_verify. Fake key and fake http only."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from ghost_credit.paystack import NOT_FOUND, UNAVAILABLE
from ghost_credit.pipeline import make_paystack_verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5)
EMPTY_LIST = json.dumps({"status": True, "data": []}).encode()


def test_key_is_read_at_call_time_and_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Authorization header carries the key set when the call is made."""
    http = RecordingHttp(200, EMPTY_LIST)
    call = make_paystack_verify(http)
    key = fake_key("helper")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", key)  # set after the callable was made
    result = call(make_parsed(), NOW)
    assert len(http.calls) == 1
    assert http.calls[0][1]["Authorization"] == "Bearer " + key
    assert result.status == NOT_FOUND


@pytest.mark.parametrize("value", [None, ""])
def test_no_key_means_no_http_call(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """With the variable unset or empty, nothing is sent and the result is UNAVAILABLE."""
    if value is None:
        monkeypatch.delenv("PAYSTACK_SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("PAYSTACK_SECRET_KEY", value)
    http = RecordingHttp(200, EMPTY_LIST)
    result = make_paystack_verify(http)(make_parsed(), NOW)
    assert http.calls == []
    assert result.status == UNAVAILABLE
    assert result.checked is False
