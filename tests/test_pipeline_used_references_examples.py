"""Example tests for the used-payment ledger in run_check. Fakes only."""

from __future__ import annotations

import json
import threading
from datetime import datetime

import pytest

from ghost_credit import paystack
from ghost_credit.paystack import NOT_FOUND, REASON_ALREADY_USED, PaystackResult
from ghost_credit.pipeline import InMemoryUsedReferences, run_check
from paystack_fakes import RecordingHttp, fake_key
from pipeline_fakes import FakePaystack, SAMPLE_SMS

NOW = datetime(2026, 11, 20, 10, 5)
TX = {"status": "success", "currency": "NGN", "amount": 4500000, "reference": "ref-1"}


class SpyLedger(InMemoryUsedReferences):
    """A ledger that records mark_used calls and can raise."""

    def __init__(self, mark_raises: bool = False, is_used_raises: bool = False) -> None:
        super().__init__()
        self.marks: list[str] = []
        self.mark_raises = mark_raises
        self.is_used_raises = is_used_raises

    def is_used(self, reference: str) -> bool:
        if self.is_used_raises:
            raise RuntimeError("ledger broke")
        return super().is_used(reference)

    def mark_used(self, reference: str) -> None:
        self.marks.append(reference)
        if self.mark_raises:
            raise RuntimeError("mark broke")
        super().mark_used(reference)


@pytest.fixture
def fake_paystack_http(monkeypatch: pytest.MonkeyPatch) -> RecordingHttp:
    """Set a fake key and replace default_http, so no real call can happen."""
    http = RecordingHttp(body=json.dumps({"data": [TX]}).encode())
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", fake_key("ledger"))
    monkeypatch.setattr(paystack, "default_http", http)
    return http


def _check(**kwargs):
    return run_check(SAMPLE_SMS, "GTBank", None, "spa", NOW, **kwargs)


def test_no_ledger_behaviour_unchanged(fake_paystack_http: RecordingHttp) -> None:
    """Without a ledger, a matching payment confirms every time."""
    assert _check().verdict.code == "CONFIRMED"
    assert _check().verdict.code == "CONFIRMED"


def test_first_check_confirms_and_marks_once(fake_paystack_http: RecordingHttp) -> None:
    """A first matching payment is CONFIRMED and marks its reference once."""
    ledger = SpyLedger()
    result = _check(used_references=ledger)
    assert result.verdict.code == "CONFIRMED"
    assert ledger.marks == ["ref-1"]


def test_second_check_is_not_found_and_marks_nothing(
    fake_paystack_http: RecordingHttp,
) -> None:
    """The same reference again gives NOT_FOUND with the used reason."""
    ledger = SpyLedger()
    _check(used_references=ledger)
    second = _check(used_references=ledger)
    assert second.verdict.code == "NOT_FOUND"
    assert second.verdict.reasons == [REASON_ALREADY_USED]
    assert second.paystack_result.reason == REASON_ALREADY_USED
    assert ledger.marks == ["ref-1"]


def test_mark_used_error_leaves_result(fake_paystack_http: RecordingHttp) -> None:
    """A mark_used that raises does not change the CONFIRMED result."""
    result = _check(used_references=SpyLedger(mark_raises=True))
    assert result.verdict.code == "CONFIRMED"


def test_is_used_error_is_not_confirmed(fake_paystack_http: RecordingHttp) -> None:
    """A ledger that cannot answer gives UNAVAILABLE and no CONFIRMED."""
    ledger = SpyLedger(is_used_raises=True)
    result = _check(used_references=ledger)
    assert result.paystack_result.status == "UNAVAILABLE"
    assert result.paystack_result.checked is False
    assert result.verdict.code != "CONFIRMED"
    assert ledger.marks == []


def test_not_confirmed_never_marks() -> None:
    """A NOT_FOUND verdict makes no mark_used call."""
    ledger = SpyLedger()
    result = PaystackResult(NOT_FOUND, True, "ref-1", None, None, "x")
    _check(used_references=ledger, paystack_verify=FakePaystack(result))
    assert ledger.marks == []


def test_injected_paystack_is_used_as_supplied() -> None:
    """An injected callable skips the ledger check but a CONFIRMED still marks."""
    ledger = SpyLedger()
    confirmed = PaystackResult("CONFIRMED", True, "ref-7", 4500000, None, "ok")
    result = _check(used_references=ledger, paystack_verify=FakePaystack(confirmed))
    assert result.verdict.code == "CONFIRMED"
    assert ledger.marks == ["ref-7"]


def test_confirmed_without_string_reference_does_not_mark() -> None:
    """No string reference means nothing to mark."""
    ledger = SpyLedger()
    confirmed = PaystackResult("CONFIRMED", True, None, 4500000, None, "ok")
    _check(used_references=ledger, paystack_verify=FakePaystack(confirmed))
    assert ledger.marks == []


def test_in_memory_ledger_is_thread_safe() -> None:
    """Many threads marking different references lose none."""
    ledger = InMemoryUsedReferences()

    def work(start: int) -> None:
        for i in range(start, start + 100):
            ledger.mark_used(f"r{i}")

    threads = [threading.Thread(target=work, args=(n * 100,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(ledger.is_used(f"r{i}") for i in range(800))
    assert not ledger.is_used("other")
