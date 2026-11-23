"""Feature: verdict-engine, Property 16: TemplateExplainer text is short, plain and ordered."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import RED_FLAG_CODES
from ghost_credit.verdict import (
    CHECK_REMINDER,
    CONFIRMED,
    OWNER_LABELS,
    TemplateExplainer,
    decide,
)
from verdict_helpers import lookup_results, paystack_inputs, parsed_alerts

CODE_NAMES = list(RED_FLAG_CODES) + ["TRANSFER_REQUEST_WORDING", "NOT_FOUND"]
NOTES = st.lists(st.sampled_from([
    "Large amount. Take extra care before releasing goods.",
    "Sent late on a Friday or at the weekend, a common time for fake alerts.",
]), max_size=3, unique=True)


@settings(max_examples=100)
@given(parsed=parsed_alerts, paystack=paystack_inputs, lookup=lookup_results, notes=NOTES)
def test_template_text_shape(parsed, paystack, lookup, notes) -> None:
    """**Validates: Requirements 6.3, 6.4, 6.5, 6.6**"""
    verdict = decide(parsed, paystack, lookup)
    text = TemplateExplainer().explain(verdict, parsed, notes)
    assert text.startswith(OWNER_LABELS[verdict.code])
    head, _, tail = text.partition("\n\nWhy:")
    assert head.count(". ") + 1 <= 3
    items = [l for l in tail.splitlines() if l.startswith("- ")]
    n_reasons = min(3, len(verdict.reasons))
    assert items[:n_reasons] == [f"- {r}" for r in verdict.reasons[:n_reasons]]
    assert items[n_reasons:] == [f"- {n}" for n in notes]
    for name in CODE_NAMES:
        assert name not in text
    if verdict.code == CONFIRMED:
        assert not text.endswith(CHECK_REMINDER)
    else:
        assert text.endswith(CHECK_REMINDER)
