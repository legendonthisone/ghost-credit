"""Example tests for Paystack and Signals failures in the pipeline."""

from __future__ import annotations

from datetime import datetime
from unittest import mock

from ghost_credit import pipeline
from ghost_credit.parser import ParsedAlert
from ghost_credit.paystack import CONFIRMED, UNAVAILABLE, PaystackResult
from ghost_credit.pipeline import _check_paystack, run_check
from pipeline_fakes import (
    FakePaystack,
    RecordingNetwork,
    RecordingReader,
    SAMPLE_SMS,
    alert_with_amount,
)

NOW = datetime(2026, 11, 20, 10, 5)


def test_paystack_that_raises_gives_unavailable_and_check_continues() -> None:
    """A raising Paystack callable gives UNAVAILABLE and a normal reply."""
    result = run_check(
        SAMPLE_SMS, "GTBank", None, "spa", NOW,
        paystack_verify=FakePaystack(raises=True), network=RecordingNetwork(),
    )
    assert result.paystack_result.status == UNAVAILABLE
    assert result.paystack_result.checked is False
    assert result.verdict.code == "UNVERIFIED"
    assert result.parsed.amount_kobo == 4500000


def test_paystack_junk_gives_unavailable() -> None:
    """A value that is not a PaystackResult is replaced by UNAVAILABLE."""
    result = run_check(
        SAMPLE_SMS, "GTBank", None, "spa", NOW,
        paystack_verify=FakePaystack({"status": "CONFIRMED"}), network=RecordingNetwork(),
    )
    assert result.paystack_result.status == UNAVAILABLE
    assert result.verdict.code != "CONFIRMED"


def test_unavailable_result_is_passed_on_unchanged() -> None:
    """An UNAVAILABLE result from Paystack is stored as the same object."""
    given = PaystackResult(UNAVAILABLE, False, None, None, None, "no Paystack key set")
    result = run_check(
        SAMPLE_SMS, "GTBank", None, "spa", NOW,
        paystack_verify=FakePaystack(given), network=RecordingNetwork(),
    )
    assert result.paystack_result is given
    assert _check_paystack(FakePaystack(given), ParsedAlert(), NOW) is given


def test_paystack_gets_merged_alert_and_same_now() -> None:
    """The callable is called once with the merged alert and the same now object."""
    paystack = FakePaystack(PaystackResult(CONFIRMED, True, "ref1", 4500000, None, "ok"))
    result = run_check(
        SAMPLE_SMS, "GTBank", None, "spa", NOW,
        paystack_verify=paystack, network=RecordingNetwork(),
    )
    assert len(paystack.calls) == 1
    assert paystack.calls[0][0] is result.parsed
    assert paystack.calls[0][1] is NOW
    assert result.verdict.code == "CONFIRMED"


def test_signals_builder_that_raises_means_no_lookup_and_no_report() -> None:
    """If Signals cannot be built, the network hears nothing and the check goes on."""
    network = RecordingNetwork()
    with mock.patch.object(pipeline, "build_signals", side_effect=ValueError("boom")):
        result = run_check(
            None, None, b"image", "spa", NOW,
            reader=RecordingReader(alert_with_amount()),
            paystack_verify=FakePaystack(raises=True), network=network,
        )
    assert network.lookups == []
    assert network.reports == []
    assert result.verdict.code == "UNVERIFIED"
    assert result.parsed.amount_kobo == 4500000
