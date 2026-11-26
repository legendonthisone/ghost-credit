"""Example tests for the already-used rule. Fake key and fake http only."""

from __future__ import annotations

import json
from datetime import datetime

from ghost_credit.paystack import (
    REASON_ALREADY_USED,
    REASON_INTERNAL,
    REASON_NO_MATCH,
    verify,
)
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
AMOUNT = 4500000
EXACT = "This payment was already used for an earlier check"


def _tx(reference: object = "ref-1", amount: object = AMOUNT) -> dict:
    """A synthetic successful NGN transaction."""
    return {"status": "success", "currency": "NGN", "amount": amount,
            "reference": reference}


def _by_reference(is_used, tx: dict | None = None):
    """Run verify on the reference path and return (result, fake)."""
    fake = RecordingHttp(body=json.dumps({"data": tx or _tx()}).encode())
    parsed = make_parsed(claimed_reference="ref-1")
    return verify(parsed, fake_key(), NOW, http=fake, is_used=is_used), fake


def _by_search(is_used, items: list):
    """Run verify on the search path and return (result, fake)."""
    fake = RecordingHttp(body=json.dumps({"data": items}).encode())
    return verify(make_parsed(), fake_key(), NOW, http=fake, is_used=is_used), fake


def test_constant_text_and_length() -> None:
    """The constant is the exact sentence and has 50 characters."""
    assert REASON_ALREADY_USED == EXACT
    assert len(REASON_ALREADY_USED) == 50


def test_used_reference_gives_not_found() -> None:
    """A used reference is NOT_FOUND, checked, with the reference kept."""
    asked: list[str] = []

    def is_used(reference: str) -> bool:
        asked.append(reference)
        return True

    result, _ = _by_reference(is_used)
    assert (result.status, result.checked) == ("NOT_FOUND", True)
    assert result.matched_reference == "ref-1"
    assert result.amount_kobo is None and result.paid_at is None
    assert result.reason == EXACT
    assert asked == ["ref-1"]


def test_unused_reference_is_confirmed() -> None:
    """An unused reference stays CONFIRMED."""
    result, _ = _by_reference(lambda reference: False)
    assert result.status == "CONFIRMED"
    assert result.matched_reference == "ref-1"


def test_no_ledger_is_confirmed() -> None:
    """With no is_used, the result is CONFIRMED as before."""
    result, _ = _by_reference(None)
    assert result.status == "CONFIRMED"


def test_raising_ledger_gives_unavailable() -> None:
    """A ledger that raises must never give CONFIRMED."""
    def is_used(reference: str) -> bool:
        raise RuntimeError("ledger broke")

    result, _ = _by_reference(is_used)
    assert (result.status, result.checked) == ("UNAVAILABLE", False)
    assert result.reason == REASON_INTERNAL == "could not check Paystack"


def test_non_bool_ledger_answer_gives_unavailable() -> None:
    """Only exactly True or False is accepted."""
    result, _ = _by_reference(lambda reference: 1)  # type: ignore[arg-type,return-value]
    assert (result.status, result.checked) == ("UNAVAILABLE", False)


def test_used_reference_on_search_path() -> None:
    """The search path gives the same NOT_FOUND for a used reference."""
    result, _ = _by_search(lambda reference: True, [_tx("ref-9")])
    assert (result.status, result.checked) == ("NOT_FOUND", True)
    assert result.matched_reference == "ref-9"
    assert result.reason == EXACT


def test_search_match_without_string_reference_skips_ledger() -> None:
    """A single match with no string reference is CONFIRMED and asks nothing."""
    calls: list[str] = []
    result, _ = _by_search(lambda reference: calls.append(reference) or True,
                           [_tx(reference=None)])
    assert result.status == "CONFIRMED"
    assert calls == []


def test_ledger_not_called_without_a_match() -> None:
    """A non-matching reply never reaches the ledger."""
    calls: list[str] = []
    result, _ = _by_reference(lambda reference: calls.append(reference) or True,
                              _tx(amount=AMOUNT + 1))
    assert result.status == "NOT_FOUND" and result.reason == REASON_NO_MATCH
    assert calls == []
