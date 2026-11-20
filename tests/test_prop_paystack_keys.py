"""Property 4: only test keys reach Paystack."""

from __future__ import annotations

from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit import paystack
from paystack_fakes import RecordingHttp, make_parsed

NOW = datetime(2026, 11, 20, 10, 2, 11)
PREFIX = "sk_" + "test_"

bad_keys = st.one_of(
    st.none(),
    st.just(""),
    st.integers(),
    st.binary(),
    st.lists(st.integers(), max_size=3),
    st.text().filter(lambda s: s != "" and not s.startswith(PREFIX)),
)
weird_parsed = st.one_of(st.none(), st.integers(), st.just(make_parsed()))


# Feature: paystack-verifier, Property 4: Only test keys reach Paystack
@settings(max_examples=200)
@given(key=bad_keys, parsed=weird_parsed)
def test_bad_key_never_calls_http(key: object, parsed: object) -> None:
    """**Validates: Requirements 2.1, 2.2, 2.3**"""
    http = RecordingHttp()
    result = paystack.verify(parsed, key, NOW, http=http)  # type: ignore[arg-type]
    expected = (paystack.REASON_NOT_TEST_KEY
                if isinstance(key, str) and key else paystack.REASON_NO_KEY)
    assert result.status == "UNAVAILABLE"
    assert result.checked is False
    assert result.reason == expected
    assert http.calls == []
