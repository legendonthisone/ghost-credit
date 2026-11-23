"""Feature: verdict-engine, Property 4: A screenshot never confirms by itself."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import ParsedAlert
from ghost_credit.verdict import decide
from verdict_helpers import lookup_results, not_confirmed_results

_phash = st.text(alphabet="0123456789abcdef", min_size=16, max_size=16).map(
    lambda h: "phash:" + h
)


@settings(max_examples=200)
@given(phash=_phash, paystack=not_confirmed_results, lookup=lookup_results)
def test_screenshot_without_flags_is_not_confirmed(phash, paystack, lookup) -> None:
    """**Validates: Requirements 2.4, 8.3**"""
    parsed = ParsedAlert(screenshot_phash=phash, red_flags=[])
    assert decide(parsed, paystack, lookup).code != "CONFIRMED"
