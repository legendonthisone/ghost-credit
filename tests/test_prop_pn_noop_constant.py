"""Property test: NoopPatternNetwork gives the same answer whatever it is asked."""

from __future__ import annotations

from hypothesis import given, settings

from ghost_credit.pattern_network import NoopPatternNetwork

import pn_strategies as S

_LOOKUP = {
    "schema_version": "1.0",
    "network_available": False,
    "matched": False,
    "matches": [],
    "trace_url": None,
}
_REPORT = {
    "schema_version": "1.0",
    "accepted": False,
    "status": "disabled",
    "pattern_id": None,
    "trace_url": None,
}


@settings(max_examples=100)
@given(S.signals, S.verdicts)
def test_noop_answers_are_constant(signals, verdict) -> None:
    """Feature: pattern-network-hook, Property 6: Noop answers are constant.

    **Validates: Requirements 4.1, 4.2, 4.5**
    """
    net = NoopPatternNetwork()
    assert net.lookup_patterns(signals).to_dict() == _LOOKUP
    assert net.report_pattern(verdict, signals).to_dict() == _REPORT
