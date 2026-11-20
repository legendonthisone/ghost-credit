"""Property test: CONFIRMED needs every condition."""

from __future__ import annotations

import json
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
TEST_PREFIX = "sk_" + "test_"

amounts = st.integers(0, 5)  # small range so matches happen often
tx_amounts = st.one_of(amounts, st.floats(0, 5, allow_nan=False), st.booleans(),
                       st.text(max_size=2), st.none())
transactions = st.fixed_dictionaries({
    "status": st.sampled_from(["success", "failed", "SUCCESS", None]),
    "currency": st.sampled_from(["NGN", "USD", "ngn", None]),
    "amount": tx_amounts,
    "reference": st.one_of(st.none(), st.text(max_size=5)),
})
keys = st.one_of(st.none(), st.text(max_size=8), st.text(max_size=4).map(fake_key),
                 st.text(max_size=4).map(lambda t: "sk_" + "live_" + t))


def _is_exact_match(tx: object, amount: int) -> bool:
    """Independent restatement of the CONFIRMED conditions."""
    return (isinstance(tx, dict) and tx.get("status") == "success"
            and tx.get("currency") == "NGN" and type(tx.get("amount")) is int
            and tx.get("amount") == amount)


# Feature: paystack-verifier, Property 13: CONFIRMED needs every condition
# **Validates: Requirements 7.5**
@settings(max_examples=200, deadline=None)
@given(key=keys, amount=amounts, use_reference=st.booleans(),
       txs=st.lists(transactions, max_size=4))
def test_confirmed_needs_every_condition(key, amount, use_reference, txs):
    data = txs[0] if (use_reference and txs) else txs
    fake = RecordingHttp(body=json.dumps({"data": data}).encode())
    ref = "ref-1" if (use_reference and txs) else None
    parsed = make_parsed(amount_kobo=amount, claimed_reference=ref)

    result = verify(parsed, key, NOW, http=fake)

    if result.status == "CONFIRMED":
        assert result.checked is True
        assert isinstance(key, str) and key.startswith(TEST_PREFIX)
        assert len(fake.calls) == 1
        assert result.amount_kobo == amount
        candidates = [data] if ref else data
        assert any(_is_exact_match(t, amount) for t in candidates)
