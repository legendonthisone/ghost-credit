"""Property test: the edit signs flag follows the JSON boolean true only."""
from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from ghost_credit.screenshot import build_alert_from_response

PHASH = "phash:0123456789abcdef"

_json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(max_size=20),
    lambda kids: st.lists(kids, max_size=3)
    | st.dictionaries(st.text(max_size=8), kids, max_size=3),
    max_leaves=8,
)


# Feature: screenshot-reader, Property 5: Edit signs flag follows the JSON boolean true
@settings(max_examples=200, deadline=None)
@given(value=_json_values)
def test_prop_edit_signs(value: object) -> None:
    """**Validates: Requirements 6.1, 6.2, 6.3, 6.4**"""
    alert = build_alert_from_response(json.dumps({"edit_signs": value}), PHASH)
    expected = ["SCREENSHOT_EDIT_SIGNS"] if value is True else []
    assert alert.red_flags == expected


def test_edit_signs_absent_and_special_values() -> None:
    """**Validates: Requirements 6.2**"""
    for text in ("{}", '{"edit_signs": null}', '{"edit_signs": 1}', '{"edit_signs": "true"}'):
        assert build_alert_from_response(text, PHASH).red_flags == []
    assert build_alert_from_response('{"edit_signs": true}', PHASH).red_flags == [
        "SCREENSHOT_EDIT_SIGNS"
    ]
