"""Examples: missing key, non-test key and unreadable amount."""

from __future__ import annotations

from datetime import datetime

from ghost_credit import paystack
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 2, 11)


def test_missing_key() -> None:
    """A None key gives UNAVAILABLE, unchecked, and no call."""
    http = RecordingHttp()
    result = paystack.verify(make_parsed(), None, NOW, http=http)
    assert (result.status, result.checked, result.reason) == (
        "UNAVAILABLE", False, "no Paystack key set")
    assert http.calls == []


def test_empty_key() -> None:
    """An empty key counts as missing."""
    http = RecordingHttp()
    result = paystack.verify(make_parsed(), "", NOW, http=http)
    assert result.reason == "no Paystack key set"
    assert http.calls == []


def test_non_test_key() -> None:
    """A key without the test prefix is refused before any call."""
    http = RecordingHttp()
    other = "sk_" + "other_" + "abc"
    result = paystack.verify(make_parsed(), other, NOW, http=http)
    assert (result.status, result.checked, result.reason) == (
        "UNAVAILABLE", False, "test keys only during the hackathon")
    assert http.calls == []
    assert other not in repr(result)


def test_bad_key_beats_bad_parsed() -> None:
    """The key is checked before the alert is read."""
    http = RecordingHttp()
    result = paystack.verify(object(), None, NOW, http=http)  # type: ignore[arg-type]
    assert result.reason == "no Paystack key set"


def test_unreadable_amount() -> None:
    """A None amount gives NOT_FOUND, unchecked, and no call."""
    http = RecordingHttp()
    result = paystack.verify(make_parsed(amount_kobo=None), fake_key(), NOW, http=http)
    assert (result.status, result.checked, result.reason) == (
        "NOT_FOUND", False, "could not read the amount")
    assert result.matched_reference is None and result.amount_kobo is None
    assert http.calls == []


def test_bool_amount_is_unreadable() -> None:
    """True is not accepted as the amount 1."""
    http = RecordingHttp()
    result = paystack.verify(make_parsed(amount_kobo=True), fake_key(), NOW, http=http)
    assert result.reason == "could not read the amount"
    assert http.calls == []
