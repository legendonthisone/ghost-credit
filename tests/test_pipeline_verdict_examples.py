"""Example tests for each verdict path through run_check."""

from __future__ import annotations

from datetime import datetime
from unittest import mock

import pytest

from ghost_credit import pipeline
from ghost_credit.parser import ParsedAlert
from ghost_credit.pattern_network import LookupResult, Match
from ghost_credit.paystack import CONFIRMED, NOT_FOUND, UNAVAILABLE, PaystackResult
from ghost_credit.pipeline import run_check
from ghost_credit.verdict import CHECK_REMINDER
from pipeline_fakes import (
    FakePaystack,
    RecordingNetwork,
    RecordingReader,
    SAMPLE_SMS,
    alert_with_amount,
    install_report_spy,
)

NOW = datetime(2026, 11, 20, 10, 5)
FOUND = PaystackResult(CONFIRMED, True, "ref1", 4500000, None, "ok")
MISSING = PaystackResult(NOT_FOUND, True, None, None, None, "none")
NO_CHECK = PaystackResult(UNAVAILABLE, False, None, None, None, "no key")


def test_confirmed_path_makes_no_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Paystack match gives CONFIRMED and nothing is reported."""
    calls = install_report_spy(monkeypatch)
    network = RecordingNetwork()
    result = run_check(SAMPLE_SMS, "GTBank", None, "spa", NOW,
                       paystack_verify=FakePaystack(FOUND), network=network)
    assert result.verdict.code == "CONFIRMED"
    assert calls == []
    assert network.reports == []


def test_not_found_path() -> None:
    """Paystack with no match gives NOT_FOUND and the reminder."""
    result = run_check(SAMPLE_SMS, "GTBank", None, "spa", NOW,
                       paystack_verify=FakePaystack(MISSING), network=RecordingNetwork())
    assert result.verdict.code == "NOT_FOUND"
    assert result.reply.endswith(CHECK_REMINDER)


def test_suspicious_path_with_red_flags() -> None:
    """No Paystack check and a red flag gives SUSPICIOUS."""
    reader = RecordingReader(alert_with_amount(red_flags=["SCREENSHOT_EDIT_SIGNS"]))
    result = run_check(None, None, b"image", "spa", NOW, reader=reader,
                       paystack_verify=FakePaystack(NO_CHECK), network=RecordingNetwork())
    assert result.verdict.code == "SUSPICIOUS"
    assert result.reply.endswith(CHECK_REMINDER)


def test_unverified_path() -> None:
    """No Paystack check and no flags gives UNVERIFIED."""
    reader = RecordingReader(alert_with_amount())
    result = run_check(None, None, b"image", "spa", NOW, reader=reader,
                       paystack_verify=FakePaystack(NO_CHECK), network=RecordingNetwork())
    assert result.verdict.code == "UNVERIFIED"
    assert result.reply.endswith(CHECK_REMINDER)


def test_screenshot_and_text_merge_through_run_check() -> None:
    """Text values win and the screenshot fills gaps and adds its flags and hash."""
    image = ParsedAlert(amount_kobo=1, claimed_bank="Other Bank", claimed_reference="REF9",
                        red_flags=["SCREENSHOT_EDIT_SIGNS"], screenshot_phash="phash:0123456789abcdef")
    result = run_check(SAMPLE_SMS, "GTBank", b"image", "spa", NOW,
                       reader=RecordingReader(image),
                       paystack_verify=FakePaystack(NO_CHECK), network=RecordingNetwork())
    assert result.parsed.amount_kobo == 4500000
    assert result.parsed.claimed_reference == "REF9"
    assert result.parsed.screenshot_phash == "phash:0123456789abcdef"
    assert "SCREENSHOT_EDIT_SIGNS" in result.parsed.red_flags
    assert result.parsed.sender_id == "GTBank"


def test_network_match_turns_unverified_into_suspicious() -> None:
    """A network match on a flag-free alert gives SUSPICIOUS (5.6); no match gives UNVERIFIED (5.7)."""
    matched = LookupResult(True, True, [Match(pattern_id="p1")])
    reader = RecordingReader(alert_with_amount())
    with_match = run_check(None, None, b"image", "spa", NOW, reader=reader,
                           paystack_verify=FakePaystack(NO_CHECK),
                           network=RecordingNetwork(lookup=matched))
    without = run_check(None, None, b"image", "spa", NOW, reader=reader,
                        paystack_verify=FakePaystack(NO_CHECK), network=RecordingNetwork())
    assert with_match.verdict.code == "SUSPICIOUS"
    assert without.verdict.code == "UNVERIFIED"


@pytest.mark.parametrize(
    "paystack,code",
    [(MISSING, "NOT_FOUND"), (NO_CHECK, "UNVERIFIED"), (NO_CHECK, "SUSPICIOUS"), (FOUND, "CONFIRMED")],
)
def test_report_called_once_for_each_unconfirmed_code(paystack, code) -> None:
    """safe_report runs once for NOT_FOUND, SUSPICIOUS and UNVERIFIED, never for CONFIRMED."""
    flags = ["SCREENSHOT_EDIT_SIGNS"] if code == "SUSPICIOUS" else []
    reader = RecordingReader(alert_with_amount(red_flags=flags))
    with mock.patch.object(pipeline, "safe_report", wraps=pipeline.safe_report) as report:
        result = run_check(None, None, b"image", "spa", NOW, reader=reader,
                           paystack_verify=FakePaystack(paystack), network=RecordingNetwork())
    assert result.verdict.code == code
    assert report.call_count == (0 if code == "CONFIRMED" else 1)
