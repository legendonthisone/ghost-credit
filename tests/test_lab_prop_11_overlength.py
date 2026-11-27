"""Property 11: over-length Try_Form text is rejected before running a check."""

from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import SlidingWindowLimiter
from ghost_credit.lab_router import route
from lab_fakes import FIXED_NOW, FakeRunCheck, SpyStore


# Feature: the-lab, Property 11: Over-length Try_Form text is always rejected before running a check
# **Validates: Requirements 7.2**
@settings(max_examples=100, deadline=None)
@given(st.text(min_size=2001, max_size=2600))
def test_over_length_text_gets_413_and_no_check(text):
    fake = FakeRunCheck()
    store = SpyStore()
    status, _, _ = route(
        "POST", "/lab/check", None, {}, json.dumps({"text": text}).encode("utf-8"),
        now=FIXED_NOW, store=store, limiter=SlidingWindowLimiter(), run_check_fn=fake,
    )
    assert status == 413
    assert fake.calls == [] and store.saved == []
