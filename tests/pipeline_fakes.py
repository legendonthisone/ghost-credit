"""Shared fakes and generators for the check-pipeline tests.

Synthetic data only. No network, no AI, no live Paystack, no real key.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from hypothesis import strategies as st

from ghost_credit import pipeline
from ghost_credit.parser import RED_FLAG_CODES, ParsedAlert
from ghost_credit.pattern_network import (
    LookupResult,
    Match,
    PatternNetwork,
    ReportReceipt,
    Signals,
    Verdict,
)
from ghost_credit.paystack import (
    CONFIRMED,
    NOT_FOUND,
    UNAVAILABLE,
    PaystackResult,
)
from ghost_credit.verdict import Explainer

SAMPLE_SMS = (
    "GTBank Credit Alert: Acct 012****789 credited NGN 45,000.00 from AMAKA "
    "on 20-Nov-2026 10:02. Avail Bal: NGN 120,000.00"
)
SAMPLE_BYTES = b"synthetic-image-bytes"
EXTRA_FLAG = "SOME_NEW_FLAG"


def fake_key(tail: str = "abc") -> str:
    """Build an obviously fake test key from pieces (never one literal)."""
    return "sk_" + "test_" + tail


# --- Fakes ----------------------------------------------------------------


class RecordingReader:
    """A reader that counts calls and returns an alert, junk, or raises."""

    def __init__(self, alert: ParsedAlert | None = None, mode: str = "ok") -> None:
        self.alert = alert if alert is not None else ParsedAlert()
        self.mode = mode
        self.calls: list[Any] = []

    def read(self, image_bytes: Any) -> Any:
        """Record the call, then follow the mode."""
        self.calls.append(None)  # never keep the bytes
        if self.mode == "raise":
            raise RuntimeError("reader broke")
        if self.mode == "junk":
            return {"not": "an alert"}
        return self.alert


class FakePaystack:
    """A Paystack callable that records its arguments and returns or raises."""

    def __init__(self, result: Any = None, raises: bool = False) -> None:
        self.result = result
        self.raises = raises
        self.calls: list[tuple[Any, Any]] = []

    def __call__(self, parsed: Any, now: Any) -> Any:
        """Record the call, then raise or return the given object."""
        self.calls.append((parsed, now))
        if self.raises:
            raise RuntimeError("paystack broke")
        return self.result


class RecordingNetwork(PatternNetwork):
    """A network that records lookups and reports and answers as told."""

    def __init__(
        self,
        lookup: LookupResult | None = None,
        lookup_raises: bool = False,
        report_raises: bool = False,
        report_delay: float = 0.0,
        log: list[str] | None = None,
    ) -> None:
        self.lookup = lookup if lookup is not None else LookupResult(False, False, [])
        self.lookup_raises = lookup_raises
        self.report_raises = report_raises
        self.report_delay = report_delay
        self.log = log if log is not None else []
        self.lookups: list[Signals] = []
        self.reports: list[tuple[Verdict, Signals]] = []
        self.reported = threading.Event()

    def lookup_patterns(self, signals: Signals) -> LookupResult:
        """Record the Signals, then raise or answer."""
        self.lookups.append(signals)
        self.log.append("lookup")
        if self.lookup_raises:
            raise RuntimeError("lookup broke")
        return self.lookup

    def report_pattern(self, verdict: Verdict, signals: Signals) -> ReportReceipt:
        """Record the report, then raise or accept."""
        if self.report_delay:
            self.reported.wait(self.report_delay)
        self.reports.append((verdict, signals))
        self.log.append("report")
        self.reported.set()
        if self.report_raises:
            raise RuntimeError("report broke")
        return ReportReceipt(accepted=True, status="queued")


class TextExplainer(Explainer):
    """Returns fixed text. Records calls into an optional shared log."""

    def __init__(self, text: str = "Explained.", log: list[str] | None = None) -> None:
        self.text = text
        self.log = log
        self.calls = 0

    def explain(self, verdict: Verdict, parsed: Any, risk_notes: list[str]) -> Any:
        """Return the fixed text."""
        self.calls += 1
        if self.log is not None:
            self.log.append("explain")
        return self.text


class JunkExplainer(TextExplainer):
    """Returns a value that is not a string."""

    def explain(self, verdict: Verdict, parsed: Any, risk_notes: list[str]) -> Any:
        """Return a non-string."""
        super().explain(verdict, parsed, risk_notes)
        return 12345


class RaisingExplainer(TextExplainer):
    """Raises an error."""

    def explain(self, verdict: Verdict, parsed: Any, risk_notes: list[str]) -> Any:
        """Raise."""
        super().explain(verdict, parsed, risk_notes)
        raise RuntimeError("explainer broke")


def install_report_spy(monkeypatch: Any) -> list[tuple[Any, Any, Any]]:
    """Wrap pipeline.safe_report so each call is recorded, then really run it."""
    calls: list[tuple[Any, Any, Any]] = []
    real = pipeline.safe_report

    def spy(network: Any, verdict: Any, signals: Any) -> Any:
        calls.append((network, verdict, signals))
        thread = real(network, verdict, signals)
        if thread is not None:
            thread.join(2)
        return thread

    monkeypatch.setattr(pipeline, "safe_report", spy)
    return calls


def wait_for_report(network: RecordingNetwork, seconds: float = 2.0) -> bool:
    """Wait briefly for the background report thread to reach the network."""
    return network.reported.wait(seconds)


# --- Generators -----------------------------------------------------------

_words = st.text(alphabet="abcdefghij KLMNO", min_size=1, max_size=12)
_flag_pool = list(RED_FLAG_CODES) + [EXTRA_FLAG, "OTHER_FLAG"]
flag_lists = st.lists(st.sampled_from(_flag_pool), max_size=8)
naive_times = st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1))
offsets = st.builds(
    lambda minutes: timezone(timedelta(minutes=minutes)),
    st.integers(min_value=-12 * 60, max_value=14 * 60),
)
aware_times = st.builds(
    lambda moment, tz: moment.replace(tzinfo=tz), naive_times, offsets
)
nows = st.one_of(naive_times, aware_times)
any_nows = st.one_of(nows, st.none(), st.integers(), st.text(max_size=5))
kobo = st.one_of(st.none(), st.integers(min_value=0, max_value=10**10))

parsed_alerts = st.builds(
    ParsedAlert,
    amount_kobo=kobo,
    currency=st.one_of(st.none(), st.just("NGN")),
    claimed_bank=st.one_of(st.none(), _words),
    sender_id=st.one_of(st.none(), _words),
    account_masked=st.one_of(st.none(), _words),
    narration=st.one_of(st.none(), _words),
    alert_time=st.one_of(st.none(), naive_times),
    available_balance_kobo=kobo,
    claimed_reference=st.one_of(st.none(), _words),
    red_flags=flag_lists,
    screenshot_phash=st.one_of(st.none(), st.just("phash:0123456789abcdef")),
)

# An image alert that always has a whole-kobo amount (so Signals can be built).
amount_alerts = st.builds(
    ParsedAlert,
    amount_kobo=st.integers(min_value=0, max_value=10**10),
    claimed_bank=st.one_of(st.none(), _words),
    claimed_reference=st.one_of(st.none(), _words),
    red_flags=flag_lists,
    screenshot_phash=st.one_of(st.none(), st.just("phash:0123456789abcdef")),
)

texts = st.one_of(
    st.none(),
    st.just(SAMPLE_SMS),
    st.just("   \n\t"),
    st.just(""),
    st.text(max_size=30),
    st.integers(),
    st.binary(max_size=5),
)
sender_ids = st.one_of(st.none(), _words, st.integers(), st.just("GTBank"))
image_inputs = st.one_of(
    st.none(),
    st.just(b""),
    st.just(SAMPLE_BYTES),
    st.binary(max_size=30),
    st.text(max_size=5),
    st.integers(),
)
categories = st.one_of(
    st.none(),
    st.just(""),
    st.just("   "),
    st.integers(),
    st.text(max_size=10),
    st.builds(lambda s: "  " + s + " \t", _words),
    st.just("spa"),
)
modes = st.sampled_from(["ok", "raise", "junk"])


@st.composite
def paystack_results(draw: st.DrawFn) -> PaystackResult:
    """A PaystackResult in a shape that paystack.verify can return."""
    status = draw(st.sampled_from([CONFIRMED, NOT_FOUND, UNAVAILABLE]))
    checked = True if status == CONFIRMED else (
        draw(st.booleans()) if status == NOT_FOUND else False
    )
    return PaystackResult(
        status,
        checked,
        draw(st.one_of(st.none(), _words)),
        draw(kobo),
        None,
        draw(_words),
    )


@st.composite
def lookup_results(draw: st.DrawFn) -> LookupResult:
    """A LookupResult that may or may not be a network match."""
    matched = draw(st.booleans())
    matches = [Match(pattern_id="p1")] if matched else []
    return LookupResult(
        network_available=draw(st.booleans()), matched=matched, matches=matches
    )


def alert_with_amount(**fields: Any) -> ParsedAlert:
    """A synthetic alert with an amount of NGN 45,000 unless told otherwise."""
    base: dict[str, Any] = {"amount_kobo": 4500000}
    base.update(fields)
    return ParsedAlert(**base)
