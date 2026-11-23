"""Example tests for call order, failures, reports and risk notes."""

from __future__ import annotations

import time
from datetime import datetime

from ghost_credit.parser import ParsedAlert
from ghost_credit.paystack import UNAVAILABLE, PaystackResult
from ghost_credit.pipeline import FALLBACK_REASON, run_check
from ghost_credit.verdict import CHECK_REMINDER, NOTE_COLLECT, NOTE_WEEKEND
from pipeline_fakes import (
    FakePaystack,
    RaisingExplainer,
    RecordingNetwork,
    RecordingReader,
    SAMPLE_SMS,
    TextExplainer,
    alert_with_amount,
    wait_for_report,
)

NOW = datetime(2026, 11, 20, 10, 5)
NO_CHECK = PaystackResult(UNAVAILABLE, False, None, None, None, "no key")


class LoggingReader(RecordingReader):
    """A reader that notes its call in a shared log."""

    def __init__(self, alert, log):
        super().__init__(alert)
        self.log = log

    def read(self, image_bytes):
        self.log.append("read")
        return super().read(image_bytes)


class LoggingPaystack(FakePaystack):
    """A Paystack fake that notes its call in a shared log."""

    def __init__(self, result, log):
        super().__init__(result)
        self.log = log

    def __call__(self, parsed, now):
        self.log.append("paystack")
        return super().__call__(parsed, now)


def test_call_order_is_read_paystack_lookup_reply_report() -> None:
    """Steps run in the order the requirements fix."""
    log: list[str] = []
    network = RecordingNetwork(log=log)
    run_check(
        None, None, b"image", "spa", NOW,
        reader=LoggingReader(alert_with_amount(), log),
        paystack_verify=LoggingPaystack(NO_CHECK, log),
        network=network,
        explainer=TextExplainer(log=log),
    )
    assert wait_for_report(network)
    assert log == ["read", "paystack", "lookup", "explain", "report"]


def test_dependency_that_raises_reaches_the_fallback(monkeypatch) -> None:
    """An unexpected failure inside the engine gives the fixed fallback result."""
    from ghost_credit import pipeline

    def boom(*args, **kwargs):
        raise RuntimeError("engine broke")

    monkeypatch.setattr(pipeline, "decide_with_notes", boom)
    result = run_check(SAMPLE_SMS, "GTBank", None, "spa", NOW,
                       paystack_verify=FakePaystack(NO_CHECK), network=RecordingNetwork())
    assert result.verdict.code == "UNVERIFIED"
    assert result.verdict.reasons == [FALLBACK_REASON]
    assert result.reply == FALLBACK_REASON + " " + CHECK_REMINDER
    assert result.risk_notes == []
    assert result.parsed.amount_kobo == 4500000  # the merged alert is kept


def test_no_usable_source_gives_fallback_and_no_calls() -> None:
    """Blank text and empty image make no Paystack, network or explainer call."""
    paystack, network, explainer = FakePaystack(NO_CHECK), RecordingNetwork(), TextExplainer()
    result = run_check("   ", "GTBank", b"", "spa", NOW,
                       paystack_verify=paystack, network=network, explainer=explainer)
    assert result.reply == FALLBACK_REASON + " " + CHECK_REMINDER
    assert result.parsed == ParsedAlert()
    assert paystack.calls == [] and network.lookups == [] and explainer.calls == 0


def test_slow_report_does_not_delay_return() -> None:
    """A report that takes seconds does not hold up the result."""
    network = RecordingNetwork(report_delay=3.0)
    start = time.monotonic()
    run_check(None, None, b"image", "spa", NOW,
              reader=RecordingReader(alert_with_amount()),
              paystack_verify=FakePaystack(NO_CHECK), network=network)
    elapsed = time.monotonic() - start
    network.reported.set()  # release the background thread
    assert elapsed < 1.0


def test_report_that_raises_leaves_result_unchanged() -> None:
    """A failing report is dropped and the normal result comes back."""
    network = RecordingNetwork(report_raises=True)
    result = run_check(None, None, b"image", "spa", NOW,
                       reader=RecordingReader(alert_with_amount()),
                       paystack_verify=FakePaystack(NO_CHECK), network=network)
    assert wait_for_report(network)
    assert result.verdict.code == "UNVERIFIED"
    assert result.reply != FALLBACK_REASON + " " + CHECK_REMINDER


def test_raising_explainer_still_gives_reply_with_reminder() -> None:
    """A broken explainer is handled by build_reply; the verdict stays."""
    result = run_check(None, None, b"image", "spa", NOW,
                       reader=RecordingReader(alert_with_amount()),
                       paystack_verify=FakePaystack(NO_CHECK), network=RecordingNetwork(),
                       explainer=RaisingExplainer())
    assert result.verdict.code == "UNVERIFIED"
    assert result.reply.endswith(CHECK_REMINDER)


def test_risk_notes_from_friday_afternoon_alert() -> None:
    """An alert time on Friday afternoon adds the weekend note."""
    friday = datetime(2026, 11, 20, 15, 0)
    result = run_check(None, None, b"image", "spa", NOW,
                       reader=RecordingReader(alert_with_amount(alert_time=friday)),
                       paystack_verify=FakePaystack(NO_CHECK), network=RecordingNetwork())
    assert NOTE_WEEKEND in result.risk_notes


def test_risk_notes_from_rider_in_alert_text() -> None:
    """Text that mentions a rider adds the collection note."""
    result = run_check(SAMPLE_SMS + " Rider is outside", "GTBank", None, "spa", NOW,
                       paystack_verify=FakePaystack(NO_CHECK), network=RecordingNetwork())
    assert NOTE_COLLECT in result.risk_notes
