"""Whole check with PATTERN_NETWORK=off and every default dependency."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from ghost_credit.pipeline import CheckResult, run_check
from ghost_credit.verdict import CHECK_REMINDER
from pipeline_fakes import SAMPLE_SMS


def test_run_check_with_all_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults (fake reader, no Paystack key, Noop network, template reply) work offline."""
    monkeypatch.setenv("PATTERN_NETWORK", "off")
    monkeypatch.delenv("PAYSTACK_SECRET_KEY", raising=False)
    # conftest makes any socket creation fail, so a stray network call would raise.
    result = run_check(SAMPLE_SMS, "GTBank", None, "spa", datetime(2026, 11, 20, 10, 5))
    assert isinstance(result, CheckResult)
    assert uuid.UUID(result.check_id).version == 4
    assert result.verdict.code in {"SUSPICIOUS", "UNVERIFIED"}
    assert result.paystack_result.status == "UNAVAILABLE"
    assert result.parsed.amount_kobo == 4500000
    assert result.reply.endswith(CHECK_REMINDER)
