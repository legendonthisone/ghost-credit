"""Property test that the secret key never leaks out of verify."""

from __future__ import annotations

import logging
from datetime import datetime

from hypothesis import HealthCheck, given, settings, strategies as st

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
tails = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=6, max_size=24)
refs = st.one_of(st.none(), st.text(alphabet="GC-0123456789", min_size=1, max_size=12))
bodies = st.one_of(st.binary(max_size=60), st.just(b'{"data": []}'),
                   st.just(b'{"data": {"status": "success"}}'))
statuses = st.sampled_from([200, 401, 404, 500])
failures = st.one_of(st.none(), st.just(TimeoutError("slow")))


# Feature: paystack-verifier, Property 5: The key never leaks
# **Validates: Requirements 2.4, 2.5, 4.2, 8.9**
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(tail=tails, ref=refs, body=bodies, status=statuses, raises=failures)
def test_key_only_in_authorization_header(caplog, tail, ref, body, status, raises):
    key = fake_key(tail)
    fake = RecordingHttp(status=status, body=body, raises=raises)
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        result = verify(make_parsed(claimed_reference=ref), key, NOW, http=fake)
    assert key not in repr(result)
    assert key not in caplog.text
    url, headers, _ = fake.calls[0]
    assert key not in url
    assert headers == {"Authorization": "Bearer " + key}
