"""Property test: a non-success status is never confirmed."""

from __future__ import annotations

import json
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
AMOUNT = 4500000

bad_status = st.one_of(
    st.text(max_size=12).filter(lambda s: s != "success"),
    st.sampled_from(["SUCCESS", "Success", " success", "success ", "failed", "abandoned"]),
    st.none(), st.booleans(), st.integers(), st.lists(st.text(max_size=3), max_size=2),
)


def _tx(status: object) -> dict:
    return {"status": status, "currency": "NGN", "amount": AMOUNT, "reference": "r1"}


# Feature: paystack-verifier, Property 3: A non-success status is never confirmed
# **Validates: Requirements 5.11, 7.5, 8.7**
@settings(max_examples=100, deadline=None)
@given(status=bad_status, use_reference=st.booleans(), count=st.integers(1, 3))
def test_non_success_status_is_never_confirmed(status, use_reference, count):
    data = _tx(status) if use_reference else [_tx(status) for _ in range(count)]
    fake = RecordingHttp(body=json.dumps({"data": data}).encode())
    parsed = make_parsed(amount_kobo=AMOUNT,
                         claimed_reference="ref-1" if use_reference else None)

    result = verify(parsed, fake_key(), NOW, http=fake)

    assert result.status != "CONFIRMED"
