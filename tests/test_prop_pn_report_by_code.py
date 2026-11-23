"""Property test: a report is sent for every verdict except CONFIRMED."""

from __future__ import annotations

from hypothesis import given, settings

from ghost_credit.pattern_network import (
    NoopPatternNetwork,
    PatternNetwork,
    ReportReceipt,
    safe_report,
)

import pn_strategies as S


class Recorder(PatternNetwork):
    """A network that records every report it receives."""

    def __init__(self) -> None:
        self.reports = []

    def lookup_patterns(self, signals):  # pragma: no cover - not used here
        raise NotImplementedError

    def report_pattern(self, verdict, signals):
        self.reports.append((verdict, signals))
        return ReportReceipt(accepted=True, status="queued")


@settings(max_examples=100)
@given(S.verdicts, S.signals)
def test_reports_follow_verdict_code(verdict, signals) -> None:
    """Feature: pattern-network-hook, Property 17: Reports follow the verdict code.
    **Validates: Requirements 8.1, 8.2**
    """
    net = Recorder()
    worker = safe_report(net, verdict, signals)
    if worker is not None:
        worker.join(5)
    if verdict.code == "CONFIRMED":
        assert worker is None
        assert net.reports == []
    else:
        assert len(net.reports) == 1
        assert net.reports[0][0] is verdict
        assert net.reports[0][1] is signals


@settings(max_examples=20)
@given(S.verdicts, S.signals)
def test_noop_report_never_raises(verdict, signals) -> None:
    """Feature: pattern-network-hook, Property 17: Reports follow the verdict code (noop).
    **Validates: Requirements 8.1, 8.2**
    """
    worker = safe_report(NoopPatternNetwork(), verdict, signals)
    if worker is not None:
        worker.join(5)
