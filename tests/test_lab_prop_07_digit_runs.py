"""Property 7: the sanitiser removes every long digit run except in check_id."""

from __future__ import annotations

import re

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import sanitise_record
from lab_fakes import text_with_digits

_LONG_RUN = re.compile(r"\d(?:[ \-.,]*\d){6,}")
_STRING_FIELDS = ("channel", "verdict", "owner_label", "claimed_bank")
_LIST_FIELDS = ("red_flags", "reasons", "risk_notes")


@st.composite
def _records(draw):
    record = {"check_id": draw(st.sampled_from(["12345678-1234-1234", "0123456789012"]))}
    for name in _STRING_FIELDS:
        record[name] = draw(text_with_digits)
    for name in _LIST_FIELDS:
        record[name] = draw(st.lists(text_with_digits, max_size=4))
    return record


# Feature: the-lab, Property 7: The Sanitiser removes every long digit run except in check_id
# **Validates: Requirements 3.7**
@settings(max_examples=100, deadline=None)
@given(_records())
def test_no_long_digit_run_survives(record):
    out = sanitise_record(record)
    assert out["check_id"] == record["check_id"]
    for name in _STRING_FIELDS:
        assert not _LONG_RUN.search(out[name]), name
    for name in _LIST_FIELDS:
        for item in out[name]:
            assert not _LONG_RUN.search(item), name
