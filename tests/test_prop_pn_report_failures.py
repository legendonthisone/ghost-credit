"""Property test: report failures stay hidden and a slow report never blocks the caller."""

from __future__ import annotations

import threading
import time

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import (
    PatternNetwork,
    ReportReceipt,
    Signals,
    Verdict,
    safe_report,
)

import pn_strategies as S
from pn_env import FAKE_KEY, capture_logs

_not_confirmed = st.sampled_from(["NOT_FOUND", "SUSPICIOUS", "UNVERIFIED"])


class _Raises(PatternNetwork):
    """A network whose report always raises the given error."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def lookup_patterns(self, signals):  # pragma: no cover - not used here
        raise NotImplementedError

    def report_pattern(self, verdict, signals):
        raise self.error


class _Slow(PatternNetwork):
    """A network whose report waits until the test lets it go."""

    def __init__(self) -> None:
        self.release = threading.Event()

    def lookup_patterns(self, signals):  # pragma: no cover - not used here
        raise NotImplementedError

    def report_pattern(self, verdict, signals):
        self.release.wait(10)
        return ReportReceipt(accepted=True, status="queued")


_marker = st.text(alphabet="QXZJ", min_size=8, max_size=12)


@settings(max_examples=100)
@given(_not_confirmed, _marker, _marker)
def test_report_errors_are_hidden(code, ref_marker, hash_marker) -> None:
    """Feature: pattern-network-hook, Property 18: Report failures stay hidden.
    **Validates: Requirements 8.4**
    """
    signals = Signals(
        check_id="c1",
        checked_at="2026-11-20T10:40:05+01:00",
        channel="sms",
        amount_kobo=100,
        claimed_reference=ref_marker,
        payer_name_hash="hmac:" + hash_marker,
    )
    verdict = Verdict(code=code, paystack_checked=False)
    error = RuntimeError(f"{ref_marker} {hash_marker} {FAKE_KEY}")
    with capture_logs() as lines:
        worker = safe_report(_Raises(error), verdict, signals)
        worker.join(5)
    assert not worker.is_alive()
    text = "\n".join(lines)
    assert lines
    for secret in (ref_marker, hash_marker, FAKE_KEY, "c1"):
        assert secret not in text


@settings(max_examples=5, deadline=None)
@given(S.signals, _not_confirmed)
def test_slow_report_does_not_block(signals, code) -> None:
    """Feature: pattern-network-hook, Property 18: Report failures do not block.
    **Validates: Requirements 8.3**
    """
    net = _Slow()
    verdict = Verdict(code=code, paystack_checked=False)
    start = time.monotonic()
    worker = safe_report(net, verdict, signals)
    elapsed = time.monotonic() - start
    try:
        assert elapsed < 0.5
        assert worker.is_alive()
    finally:
        net.release.set()
        worker.join(5)
