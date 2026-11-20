"""Property test: paid_at handling on a confirmed reference check."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
LAGOS = timedelta(hours=1)

# Fixed offsets (whole minutes, up to 14 hours) avoid needing a tz database.
fixed_offsets = st.integers(min_value=-14 * 60, max_value=14 * 60).map(
    lambda minutes: timezone(timedelta(minutes=minutes)))
aware_times = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1),
    timezones=fixed_offsets,
)

# Values that are missing or cannot be read as an ISO 8601 time.
bad_values = st.sampled_from([
    "", "not a date", "yesterday", "2026-13-45T99:99:99", "20/11/2026", 12345, None, [],
])


def _confirm(paid_at_field: dict):
    """Run a confirmed reference check with the given paid_at entry."""
    data = {"status": "success", "currency": "NGN", "amount": 4500000}
    data.update(paid_at_field)
    fake = RecordingHttp(body=json.dumps({"data": data}).encode())
    parsed = make_parsed(claimed_reference="GC-1001")
    return verify(parsed, fake_key("paidat"), NOW, http=fake)


# Feature: paystack-verifier, Property 12: paid_at handling
# **Validates: Requirements 7.3, 7.4**
@settings(max_examples=100, deadline=None)
@given(moment=aware_times)
def test_valid_paid_at_becomes_same_instant_in_lagos(moment):
    text = moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    result = _confirm({"paid_at": text})

    assert result.status == "CONFIRMED"
    assert result.paid_at is not None
    assert result.paid_at.utcoffset() == LAGOS
    assert result.paid_at == moment


# Feature: paystack-verifier, Property 12: paid_at handling
# **Validates: Requirements 7.3, 7.4**
@settings(max_examples=100, deadline=None)
@given(bad=bad_values)
def test_unreadable_paid_at_is_none_and_still_confirmed(bad):
    result = _confirm({"paid_at": bad})

    assert result.status == "CONFIRMED"
    assert result.paid_at is None


# Feature: paystack-verifier, Property 12: paid_at handling
# **Validates: Requirements 7.4**
def test_missing_paid_at_is_none_and_still_confirmed():
    result = _confirm({})

    assert result.status == "CONFIRMED"
    assert result.paid_at is None
