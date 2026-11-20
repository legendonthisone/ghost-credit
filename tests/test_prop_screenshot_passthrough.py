"""Property test: valid values pass through and unknown keys are ignored."""
from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from ghost_credit.screenshot import build_alert_from_response

PHASH = "phash:0123456789abcdef"

_text = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=100)


@st.composite
def valid_objects(draw: st.DrawFn) -> dict:
    """Build an object with a random subset of valid allowlisted values."""
    fields = {
        "amount_kobo": st.integers(0, 10**12),
        "currency": st.just("NGN"),
        "claimed_bank": _text,
        "account_masked": _text,
        "narration": st.text(
            alphabet=st.characters(blacklist_categories=("Cs",)), max_size=400
        ),
        "alert_time": st.just("2026-03-12T10:15:00"),
        "available_balance_kobo": st.integers(0, 10**12),
        "claimed_reference": _text,
    }
    return {k: draw(s) for k, s in fields.items() if draw(st.booleans())}


_extra_values = st.none() | st.booleans() | st.integers() | st.text(max_size=50) | st.lists(
    st.integers(), max_size=3
)
extra_keys = st.dictionaries(
    st.sampled_from(
        ["red_flags", "verdict", "sender_id", "instructions", "note", "x", "CONFIRMED"]
    ),
    _extra_values,
    max_size=5,
)


# Feature: screenshot-reader, Property 2: Valid values pass through and unknown keys are ignored
@settings(max_examples=100, deadline=None)
@given(valid=valid_objects(), extra=extra_keys)
def test_prop_valid_values_and_extra_keys(valid: dict, extra: dict) -> None:
    """**Validates: Requirements 5.1, 5.10, 5.12, 5.13**"""
    plain = build_alert_from_response(json.dumps(valid), PHASH)
    noisy = build_alert_from_response(json.dumps({**valid, **extra}), PHASH)
    assert noisy == plain
    assert plain.amount_kobo == valid.get("amount_kobo")
    assert plain.currency == valid.get("currency")
    assert plain.claimed_bank == valid.get("claimed_bank")
    assert plain.account_masked == valid.get("account_masked")
    assert plain.available_balance_kobo == valid.get("available_balance_kobo")
    assert plain.claimed_reference == valid.get("claimed_reference")
    narration = valid.get("narration")
    assert plain.narration == (None if narration is None else narration[:200])
    assert (plain.alert_time is not None) == ("alert_time" in valid)
    assert plain.sender_id is None
    assert plain.red_flags == []
