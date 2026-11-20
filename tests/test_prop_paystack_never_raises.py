"""Property test: verify never raises and always returns a valid result."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import PaystackResult, verify
from paystack_fakes import fake_key, make_parsed

VALID = {"CONFIRMED", "NOT_FOUND", "UNAVAILABLE"}

scalars = st.one_of(st.none(), st.booleans(), st.integers(), st.floats(),
                    st.text(max_size=20), st.binary(max_size=10))
datetimes = st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1),
                         timezones=st.one_of(st.none(), st.just(timezone.utc)))

parsed_like = st.one_of(
    st.none(),
    st.just(object()),
    scalars,
    st.builds(make_parsed, amount_kobo=st.one_of(st.none(), st.integers(0, 10**9)),
              claimed_reference=st.one_of(st.none(), st.text(max_size=20)),
              alert_time=st.one_of(st.none(), datetimes.map(lambda d: d.replace(tzinfo=None)))),
    st.builds(SimpleNamespace, amount_kobo=scalars, claimed_reference=scalars,
              alert_time=st.one_of(scalars, datetimes)),
)
keys = st.one_of(st.none(), scalars, st.just(fake_key()), st.text(max_size=5).map(fake_key))
nows = st.one_of(datetimes, scalars)

# One fake behaviour: raise, or return an arbitrary reply of any shape.
replies = st.one_of(
    st.tuples(st.integers(-5, 700), st.binary(max_size=60)),
    st.tuples(st.just(200), st.sampled_from([b"{}", b"[]", b'{"data": []}', b'{"data": {}}',
                                              b'{"data": 5}', b"\xff\xfe"])),
    scalars,
    st.tuples(scalars, scalars),
    st.tuples(scalars, scalars, scalars),
)


def _make_http(raises: bool, reply: object):
    """Build a fake Http_Function that raises or returns ``reply``."""
    def http(url, headers, timeout_seconds):
        if raises:
            raise RuntimeError("boom " + url)
        return reply
    return http


# Feature: paystack-verifier, Property 1: Never raises, always a valid result
# **Validates: Requirements 1.4, 1.5, 1.6, 6.6, 8.5**
@settings(max_examples=200, deadline=None)
@given(parsed=parsed_like, key=keys, now=nows, raises=st.booleans(), reply=replies)
def test_verify_never_raises_and_result_is_valid(parsed, key, now, raises, reply):
    result = verify(parsed, key, now, http=_make_http(raises, reply))

    assert isinstance(result, PaystackResult)
    assert result.status in VALID
    assert 1 <= len(result.reason) <= 120
    if result.status != "CONFIRMED":
        assert result.matched_reference is None
        assert result.amount_kobo is None
        assert result.paid_at is None
    else:
        assert result.checked is True
