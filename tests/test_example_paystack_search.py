"""Example tests for the Paystack search path (no reference on the alert)."""

from __future__ import annotations

import json
from datetime import datetime

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
AMOUNT = 4500000
MANY = "more than one payment of this amount, check manually"


def _tx(reference: str = "GC-T-1", amount: int = AMOUNT) -> dict:
    return {"status": "success", "currency": "NGN", "amount": amount,
            "reference": reference, "paid_at": "2026-11-20T10:02:11+01:00"}


def _run(items: list):
    fake = RecordingHttp(body=json.dumps({"data": items}).encode())
    result = verify(make_parsed(amount_kobo=AMOUNT), fake_key(), NOW, http=fake)
    return result, fake


def test_one_match_is_confirmed():
    result, fake = _run([_tx(), _tx("GC-T-2", AMOUNT + 100)])
    assert result.status == "CONFIRMED"
    assert result.checked is True
    assert result.matched_reference == "GC-T-1"
    assert result.amount_kobo == AMOUNT
    assert len(fake.calls) == 1


def test_zero_matches_is_not_found():
    result, _ = _run([_tx(amount=AMOUNT + 1)])
    assert (result.status, result.checked) == ("NOT_FOUND", True)
    assert result.reason == "Paystack has no matching payment"


def test_two_matches_is_check_manually():
    result, _ = _run([_tx("GC-T-1"), _tx("GC-T-2")])
    assert (result.status, result.checked, result.reason) == ("NOT_FOUND", True, MANY)


def test_full_page_with_one_match_is_check_manually():
    items = [_tx("GC-T-0")] + [_tx("GC-X", AMOUNT + 1) for _ in range(99)]
    result, _ = _run(items)
    assert (result.status, result.checked, result.reason) == ("NOT_FOUND", True, MANY)


def test_non_object_item_is_skipped():
    result, _ = _run(["junk", None, 5, _tx()])
    assert result.status == "CONFIRMED"
    assert result.matched_reference == "GC-T-1"
