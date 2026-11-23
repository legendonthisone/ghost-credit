"""Property test: reports carry the check_id and owner_outcome exactly as given."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import (
    PatternNetwork,
    ReportReceipt,
    Verdict,
    safe_report,
)

import pn_strategies as S

_not_confirmed = st.sampled_from(["NOT_FOUND", "SUSPICIOUS", "UNVERIFIED"])
_outcomes = st.sampled_from(["unknown", "fake", "real"])


class _Recorder(PatternNetwork):
    """A network that records (check_id, owner_outcome) for each report."""

    def __init__(self) -> None:
        self.seen = []

    def lookup_patterns(self, signals):  # pragma: no cover - not used here
        raise NotImplementedError

    def report_pattern(self, verdict, signals):
        self.seen.append((signals.check_id, verdict.owner_outcome))
        return ReportReceipt(accepted=True, status="queued")


@settings(max_examples=100)
@given(S.signals, _not_confirmed, _outcomes, _outcomes)
def test_update_keeps_check_id_and_outcome(signals, code, first, second) -> None:
    """Feature: pattern-network-hook, Property 19: Reports pass identity and outcome through.
    **Validates: Requirements 8.5, 8.6, 8.7**
    """
    net = _Recorder()
    v1 = Verdict(code=code, paystack_checked=False, owner_outcome=first)
    v2 = replace(v1, owner_outcome=second)
    safe_report(net, v1, signals).join(5)
    safe_report(net, v2, signals).join(5)
    assert net.seen == [(signals.check_id, first), (signals.check_id, second)]


@settings(max_examples=50)
@given(S.signals, _not_confirmed)
def test_unanswered_owner_is_unknown(signals, code) -> None:
    """Feature: pattern-network-hook, Property 19: default owner_outcome is 'unknown'.
    **Validates: Requirements 8.7**
    """
    net = _Recorder()
    safe_report(net, Verdict(code=code, paystack_checked=True), signals).join(5)
    assert net.seen == [(signals.check_id, "unknown")]
