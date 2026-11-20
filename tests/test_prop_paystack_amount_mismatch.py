"""Property test: a mismatched amount is never confirmed."""

from __future__ import annotations

import json
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)


@st.composite
def amount_and_wrong(draw):
    """Draw a parsed amount and a response amount that is not an equal int."""
    amount = draw(st.integers(0, 10**9))
    wrong = draw(st.one_of(
        st.integers(0, 10**9).filter(lambda n: n != amount),
        st.just(float(amount)),
        st.floats(allow_nan=False, allow_infinity=False),
        st.just(str(amount)),
        st.text(max_size=10),
        st.booleans(),
        st.none(),
    ))
    return amount, wrong


def _tx(amount: object) -> dict:
    return {"status": "success", "currency": "NGN", "amount": amount, "reference": "r1"}


# Feature: paystack-verifier, Property 2: A mismatched amount is never confirmed
# **Validates: Requirements 4.6, 5.11, 7.5, 8.6**
@settings(max_examples=100, deadline=None)
@given(pair=amount_and_wrong(), use_reference=st.booleans(),
       count=st.integers(1, 3))
def test_mismatched_amount_is_never_confirmed(pair, use_reference, count):
    amount, wrong = pair
    # A bool is only "equal" to 0 or 1, so make sure those cases are reachable.
    data = _tx(wrong) if use_reference else [_tx(wrong) for _ in range(count)]
    fake = RecordingHttp(body=json.dumps({"data": data}, allow_nan=False).encode())
    ref = "ref-1" if use_reference else None
    parsed = make_parsed(amount_kobo=amount, claimed_reference=ref)

    result = verify(parsed, fake_key(), NOW, http=fake)

    assert result.status != "CONFIRMED"


# Feature: paystack-verifier, Property 2: A mismatched amount is never confirmed (bool edge)
# **Validates: Requirements 4.6, 5.11, 7.5, 8.6**
@settings(max_examples=100, deadline=None)
@given(amount=st.sampled_from([0, 1]), use_reference=st.booleans())
def test_bool_amount_equal_to_zero_or_one_is_not_confirmed(amount, use_reference):
    data = _tx(bool(amount)) if use_reference else [_tx(bool(amount))]
    fake = RecordingHttp(body=json.dumps({"data": data}).encode())
    parsed = make_parsed(amount_kobo=amount,
                         claimed_reference="ref-1" if use_reference else None)

    result = verify(parsed, fake_key(), NOW, http=fake)

    assert result.status != "CONFIRMED"
