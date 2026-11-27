"""Property 6: the sanitiser enforces its field and length invariants."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import (
    ALLOWED_FIELDS,
    MAX_BANK_CHARS,
    MAX_LIST_ITEMS,
    MAX_TEXT_FIELD_CHARS,
    sanitise_record,
)

_long_text = st.text(min_size=0, max_size=400)
_record = st.fixed_dictionaries(
    {},
    optional={
        "check_id": st.text(min_size=1, max_size=40),
        "checked_at": st.text(max_size=40),
        "channel": st.text(max_size=20),
        "verdict": st.text(max_size=20),
        "owner_label": st.text(max_size=20),
        "amount_kobo": st.one_of(st.none(), st.integers()),
        "claimed_bank": st.one_of(st.none(), _long_text),
        "red_flags": st.lists(_long_text, max_size=30),
        "reasons": st.lists(_long_text, max_size=30),
        "risk_notes": st.lists(_long_text, max_size=30),
        "expires_at": st.integers(),
    },
).flatmap(
    lambda base: st.dictionaries(
        st.text(min_size=1, max_size=15), st.one_of(st.text(max_size=30), st.integers()), max_size=6
    ).map(lambda extra: {**extra, **base})
)


# Feature: the-lab, Property 6: The Sanitiser enforces its field and length invariants
# **Validates: Requirements 3.6, 3.8, 3.9**
@settings(max_examples=100, deadline=None)
@given(_record)
def test_sanitiser_keeps_allowed_fields_and_cuts_lengths(record):
    out = sanitise_record(record)
    assert set(out) == {name for name in ALLOWED_FIELDS if name in record}
    for name in ("reasons", "risk_notes"):
        if name in out:
            assert len(out[name]) <= MAX_LIST_ITEMS
            assert all(len(item) <= MAX_TEXT_FIELD_CHARS for item in out[name])
    if out.get("claimed_bank") is not None:
        assert len(out["claimed_bank"]) <= MAX_BANK_CHARS
