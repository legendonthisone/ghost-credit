"""Property test: unusable model output leaves every field empty."""
from __future__ import annotations

import json

from hypothesis import assume, given, settings, strategies as st

from ghost_credit.screenshot import MAX_MODEL_OUTPUT_CHARS, build_alert_from_response

PHASH = "phash:0123456789abcdef"

_non_objects = (
    st.none() | st.booleans() | st.integers() | st.text(max_size=50)
    | st.lists(st.integers(), max_size=5)
)


def _assert_empty(text: str) -> None:
    """Check every extracted field is empty and only the hash is kept."""
    alert = build_alert_from_response(text, PHASH)
    assert alert.amount_kobo is None
    assert alert.currency is None
    assert alert.claimed_bank is None
    assert alert.account_masked is None
    assert alert.narration is None
    assert alert.alert_time is None
    assert alert.available_balance_kobo is None
    assert alert.claimed_reference is None
    assert alert.sender_id is None
    assert alert.red_flags == []
    assert alert.screenshot_phash == PHASH


# Feature: screenshot-reader, Property 3: Unusable output leaves all fields empty
@settings(max_examples=100, deadline=None)
@given(text=st.text(max_size=200))
def test_prop_not_json_object(text: str) -> None:
    """**Validates: Requirements 5.2, 5.3**"""
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
        _assert_empty(text)
        return
    assume(not isinstance(parsed, dict))
    _assert_empty(text)


@settings(max_examples=100, deadline=None)
@given(value=_non_objects)
def test_prop_valid_json_not_object(value: object) -> None:
    """**Validates: Requirements 5.2**"""
    _assert_empty(json.dumps(value))


@settings(max_examples=50, deadline=None)
@given(extra=st.integers(1, 500))
def test_prop_too_long(extra: int) -> None:
    """**Validates: Requirements 5.3**"""
    pad = " " * (MAX_MODEL_OUTPUT_CHARS + extra)
    _assert_empty('{"amount_kobo": 5000000, "currency": "NGN", "edit_signs": true}' + pad)
