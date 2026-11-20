"""Property test: reasons are always one of the fixed strings."""

from __future__ import annotations

import json
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)

FIXED_REASONS = {
    "no Paystack key set",
    "test keys only during the hackathon",
    "could not read the amount",
    "could not reach Paystack",
    "Paystack did not answer normally",
    "Paystack reply could not be read",
    "Paystack has no matching payment",
    "more than one payment of this amount, check manually",
    "Paystack has a matching payment",
    "could not check Paystack",
}

text = st.text(max_size=30)
tx = st.fixed_dictionaries({
    "status": st.one_of(text, st.just("success")),
    "currency": st.one_of(text, st.just("NGN")),
    "amount": st.one_of(text, st.integers(0, 3)),
    "reference": text,
    "paid_at": text,
    "message": text,
    "gateway_response": text,
})
bodies = st.one_of(
    st.builds(lambda d, m: {"data": d, "message": m, "status": m}, tx, text),
    st.builds(lambda d, m: {"data": d, "message": m}, st.lists(tx, max_size=3), text),
    st.builds(lambda m: {"message": m}, text),
)


# Feature: paystack-verifier, Property 14: Reasons are fixed strings
# **Validates: Requirements 7.6, 1.5**
@settings(max_examples=150, deadline=None)
@given(body=bodies, status=st.sampled_from([200, 200, 200, 401, 404, 500]),
       amount=st.one_of(st.none(), st.integers(0, 3)),
       reference=st.one_of(st.none(), text), key_tail=text,
       raise_text=st.one_of(st.none(), text))
def test_reason_is_always_a_fixed_string(body, status, amount, reference, key_tail, raise_text):
    key = fake_key(key_tail)
    raises = RuntimeError(raise_text + key) if raise_text is not None else None
    fake = RecordingHttp(status=status, body=json.dumps(body).encode(), raises=raises)
    parsed = make_parsed(amount_kobo=amount, claimed_reference=reference)

    result = verify(parsed, key, NOW, http=fake)

    assert result.reason in FIXED_REASONS
    assert key not in result.reason
