"""Example test for the Decision dataclass."""

from __future__ import annotations

import dataclasses

import pytest

from ghost_credit.parser import ParsedAlert
from ghost_credit.verdict import Decision, decide, decide_with_notes


def test_decision_is_frozen_and_holds_verdict_and_notes() -> None:
    """**Validates: Requirements 5.1, 5.2**"""
    parsed = ParsedAlert(amount_kobo=60000000)
    decision = decide_with_notes(parsed, None, None)
    assert isinstance(decision, Decision)
    assert decision.verdict == decide(parsed, None, None)
    assert decision.risk_notes == ["Large amount. Take extra care before releasing goods."]
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.verdict = decision.verdict  # type: ignore[misc]
