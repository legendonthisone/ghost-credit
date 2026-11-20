"""Property test: the search outcome depends on the match count."""

from __future__ import annotations

import json
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
AMOUNT = 4500000

MANY = "more than one payment of this amount, check manually"
NONE = "Paystack has no matching payment"


def _match(ref: object) -> dict:
    return {"status": "success", "currency": "NGN", "amount": AMOUNT, "reference": ref}


matching = st.one_of(st.text(max_size=10), st.integers(), st.none()).map(_match)
non_matching = st.one_of(
    st.just({"status": "failed", "currency": "NGN", "amount": AMOUNT}),
    st.just({"status": "success", "currency": "USD", "amount": AMOUNT}),
    st.just({"status": "success", "currency": "NGN", "amount": AMOUNT + 1}),
    st.just({"status": "success", "currency": "NGN", "amount": float(AMOUNT)}),
    st.just({"status": "success", "currency": "NGN", "amount": True}),
    st.just("not an object"),
    st.just(None),
    st.just(7),
)
items_lists = st.lists(st.one_of(matching, non_matching), max_size=120)


# Feature: paystack-verifier, Property 10: Search outcome depends on the match count
# **Validates: Requirements 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 4.5**
@settings(max_examples=100, deadline=None)
@given(items=items_lists)
def test_search_outcome_depends_on_match_count(items):
    fake = RecordingHttp(body=json.dumps({"data": items}).encode())
    parsed = make_parsed(amount_kobo=AMOUNT)

    result = verify(parsed, fake_key(), NOW, http=fake)

    matches = [
        i for i in items
        if isinstance(i, dict) and i.get("status") == "success"
        and i.get("currency") == "NGN" and type(i.get("amount")) is int
        and i.get("amount") == AMOUNT
    ]
    assert result.checked is True
    if len(matches) == 1 and len(items) < 100:
        assert result.status == "CONFIRMED"
        ref = matches[0]["reference"]
        assert result.matched_reference == (ref if isinstance(ref, str) else None)
        assert result.amount_kobo == AMOUNT
    elif not matches:
        assert (result.status, result.reason) == ("NOT_FOUND", NONE)
    else:
        assert (result.status, result.reason) == ("NOT_FOUND", MANY)
