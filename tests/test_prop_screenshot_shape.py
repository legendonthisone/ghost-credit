"""Property test: any JSON reply gives a ParsedAlert of the allowed shape."""
from __future__ import annotations

import json
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.screenshot import build_alert_from_response

_scalars = (
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=True) | st.text()
)
json_values = st.recursive(
    _scalars,
    lambda kids: st.lists(kids, max_size=4)
    | st.dictionaries(st.text(max_size=12), kids, max_size=4),
    max_leaves=15,
)

_KEYS = [
    "amount_kobo", "currency", "claimed_bank", "account_masked", "narration",
    "alert_time", "available_balance_kobo", "claimed_reference", "edit_signs",
]
# Objects that use the real keys, so the checks on each field are reached.
keyed_objects = st.dictionaries(st.sampled_from(_KEYS), json_values, max_size=9)


# Feature: screenshot-reader, Property 1: Validated output shape
@settings(max_examples=200, deadline=None)
@given(value=json_values | keyed_objects)
def test_prop_validated_shape(value: object) -> None:
    """**Validates: Requirements 5.4, 5.5, 5.6, 5.7, 5.8, 5.11, 6.3, 9.5**"""
    alert = build_alert_from_response(json.dumps(value), "phash:0123456789abcdef")
    assert alert.currency in ("NGN", None)
    for kobo in (alert.amount_kobo, alert.available_balance_kobo):
        assert kobo is None or (type(kobo) is int and kobo >= 0)
    for text in (alert.claimed_bank, alert.account_masked, alert.claimed_reference):
        assert text is None or (type(text) is str and len(text) <= 100)
    assert alert.narration is None or (
        type(alert.narration) is str and len(alert.narration) <= 200
    )
    assert alert.alert_time is None or (
        isinstance(alert.alert_time, datetime) and alert.alert_time.tzinfo is None
    )
    assert alert.sender_id is None
    assert alert.red_flags in ([], ["SCREENSHOT_EDIT_SIGNS"])
    assert alert.screenshot_phash == "phash:0123456789abcdef"
