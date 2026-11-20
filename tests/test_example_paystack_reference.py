"""Example tests for the Paystack reference check, using recorded fake replies."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
KEY = fake_key("example")
NO_MATCH = "Paystack has no matching payment"


def _reply(**data) -> RecordingHttp:
    base = {"status": "success", "currency": "NGN", "amount": 4500000,
            "reference": "GC-1001", "paid_at": "2026-11-20T09:02:11.000Z"}
    base.update(data)
    return RecordingHttp(body=json.dumps({"status": True, "data": base}).encode())


def _run(fake: RecordingHttp):
    return verify(make_parsed(claimed_reference="GC-1001"), KEY, NOW, http=fake)


def test_confirmed_reference_check():
    result = _run(_reply())

    assert result.status == "CONFIRMED"
    assert result.checked is True
    assert result.matched_reference == "GC-1001"
    assert result.amount_kobo == 4500000
    assert result.paid_at == datetime(2026, 11, 20, 10, 2, 11,
                                      tzinfo=timezone(timedelta(hours=1)))
    assert result.reason == "Paystack has a matching payment"


def test_non_ngn_currency_is_not_found():
    result = _run(_reply(currency="USD"))

    assert result.status == "NOT_FOUND"
    assert result.checked is True
    assert result.reason == NO_MATCH
    assert result.matched_reference is None


def test_bool_amount_is_not_confirmed():
    result = verify(make_parsed(amount_kobo=1, claimed_reference="GC-1001"),
                    KEY, NOW, http=_reply(amount=True))

    assert result.status == "NOT_FOUND"
    assert result.checked is True


def test_float_and_string_amounts_are_not_confirmed():
    for amount in (4500000.0, "4500000"):
        assert _run(_reply(amount=amount)).status == "NOT_FOUND"


def test_wrong_amount_and_non_success_status_are_not_found():
    assert _run(_reply(amount=4500001)).status == "NOT_FOUND"
    assert _run(_reply(status="failed")).status == "NOT_FOUND"
