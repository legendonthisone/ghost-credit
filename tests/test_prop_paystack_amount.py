"""Property 6: unreadable amounts make no call."""

from __future__ import annotations

from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit import paystack
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 2, 11)

bad_amounts = st.one_of(
    st.none(), st.booleans(), st.floats(allow_nan=True), st.text(), st.binary()
)


# Feature: paystack-verifier, Property 6: Unreadable amounts make no call
@settings(max_examples=200)
@given(amount=bad_amounts, tail=st.text(alphabet="abcdef0123456789", min_size=1, max_size=12))
def test_unreadable_amount_makes_no_call(amount: object, tail: str) -> None:
    """**Validates: Requirements 3.1, 3.2**"""
    http = RecordingHttp()
    result = paystack.verify(make_parsed(amount_kobo=amount), fake_key(tail), NOW, http=http)
    assert result.status == "NOT_FOUND"
    assert result.checked is False
    assert result.reason == "could not read the amount"
    assert http.calls == []
