"""Property test: a matching reference payment is confirmed."""

from __future__ import annotations

import json
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)

amounts = st.integers(min_value=1, max_value=10**12)
references = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")
tails = st.text(alphabet="abcdef0123456789", min_size=1, max_size=12)


# Feature: paystack-verifier, Property 9: A matching reference payment is confirmed
# **Validates: Requirements 4.3, 4.4**
@settings(max_examples=100, deadline=None)
@given(amount=amounts, reference=references, tail=tails)
def test_matching_reference_payment_is_confirmed(amount, reference, tail):
    body = json.dumps({"data": {
        "status": "success", "currency": "NGN", "amount": amount,
        "reference": "other-ref", "paid_at": "2026-11-20T09:02:11.000Z",
    }}).encode()
    fake = RecordingHttp(body=body)
    parsed = make_parsed(amount_kobo=amount, claimed_reference=reference)

    result = verify(parsed, fake_key(tail), NOW, http=fake)

    assert result.status == "CONFIRMED"
    assert result.checked is True
    assert result.matched_reference == reference
    assert result.amount_kobo == amount
    assert len(fake.calls) == 1
