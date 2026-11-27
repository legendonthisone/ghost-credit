"""Property 10: Try_Form's response fields come from the CheckResult it ran."""

from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import SlidingWindowLimiter
from ghost_credit.lab_router import route
from ghost_credit.verdict import OWNER_LABELS, TemplateExplainer
from lab_fakes import FIXED_NOW, FakeRunCheck, SpyStore, check_results


# Feature: the-lab, Property 10: Try_Form's response fields come from the CheckResult it ran
# **Validates: Requirements 7.1**
@settings(max_examples=100, deadline=None)
@given(st.text(max_size=2000), check_results)
def test_response_fields_match_the_check_result(text, result):
    fake = FakeRunCheck(result)
    store = SpyStore()
    status, _, body = route(
        "POST", "/lab/check", None, {}, json.dumps({"text": text}).encode("utf-8"),
        now=FIXED_NOW, store=store, limiter=SlidingWindowLimiter(), run_check_fn=fake,
    )
    data = json.loads(body)
    assert status == 200
    assert data == {
        "verdict": result.verdict.code,
        "owner_label": OWNER_LABELS[result.verdict.code],
        "amount_kobo": result.parsed.amount_kobo,
        "red_flags": result.parsed.red_flags,
        "reasons": result.verdict.reasons,
        "risk_notes": result.risk_notes,
        "reply": result.reply,
    }
    assert len(fake.calls) == 1 and fake.calls[0][0] == text
    assert isinstance(fake.kwargs[0]["explainer"], TemplateExplainer)
    assert len(store.saved) == 1 and store.saved[0]["channel"] == "lab"
