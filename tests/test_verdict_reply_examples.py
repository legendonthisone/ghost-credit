"""Example tests for build_reply."""

from __future__ import annotations

import pytest

from ghost_credit.pattern_network import Verdict
from ghost_credit.verdict import (
    CHECK_REMINDER,
    CONFIRMED,
    NOT_FOUND,
    SUSPICIOUS,
    UNVERIFIED,
    Explainer,
    TemplateExplainer,
    build_reply,
)

NOTE = "Large amount. Take extra care before releasing goods."


class _Raises(Explainer):
    def explain(self, verdict, parsed, risk_notes):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")


def _verdict(code: str) -> Verdict:
    return Verdict(code=code, paystack_checked=False, reasons=["First.", "Second."])


@pytest.mark.parametrize("code", [NOT_FOUND, SUSPICIOUS, UNVERIFIED])
def test_reminder_is_last_for_unconfirmed(code: str) -> None:
    """**Validates: Requirements 7.2**"""
    reply = build_reply(_verdict(code), None, TemplateExplainer(), [NOTE])
    assert reply.endswith(CHECK_REMINDER)
    assert reply.count(CHECK_REMINDER) == 1


def test_confirmed_gets_no_reminder() -> None:
    """**Validates: Requirements 7.4**"""
    reply = build_reply(_verdict(CONFIRMED), None, TemplateExplainer(), [])
    assert CHECK_REMINDER not in reply


def test_failing_explainer_falls_back_to_reasons_and_notes() -> None:
    """**Validates: Requirements 6.11**"""
    reply = build_reply(_verdict(SUSPICIOUS), None, _Raises(), [NOTE])
    assert reply == f"First. Second.\n{NOTE}\n{CHECK_REMINDER}"
