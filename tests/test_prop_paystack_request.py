"""Property test for the Paystack request that verify builds."""

from __future__ import annotations

import urllib.parse
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import _iso, _search_window, verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
tails = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=20)
amounts = st.integers(min_value=1, max_value=10**10)
references = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")
blank_refs = st.one_of(st.none(), st.just(""), st.text(alphabet=" \t\n", max_size=5))
alert_times = st.one_of(st.none(), st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1)))


# Feature: paystack-verifier, Property 7: Request building
# **Validates: Requirements 4.1, 4.2, 4.7, 5.1, 6.5**
@settings(max_examples=150)
@given(tail=tails, amount=amounts, reference=references)
def test_reference_request(tail, amount, reference):
    fake = RecordingHttp()
    key = fake_key(tail)
    verify(make_parsed(amount_kobo=amount, claimed_reference=reference), key, NOW, http=fake)
    assert len(fake.calls) == 1
    url, headers, timeout = fake.calls[0]
    assert url == "https://api.paystack.co/transaction/verify/" + urllib.parse.quote(reference, safe="")
    assert headers == {"Authorization": "Bearer " + key}
    assert timeout == 5


# Feature: paystack-verifier, Property 7: Request building (search form)
# **Validates: Requirements 5.1, 6.5**
@settings(max_examples=150)
@given(tail=tails, amount=amounts, reference=blank_refs, alert_time=alert_times)
def test_search_request(tail, amount, reference, alert_time):
    fake = RecordingHttp()
    key = fake_key(tail)
    verify(make_parsed(amount_kobo=amount, claimed_reference=reference,
                       alert_time=alert_time), key, NOW, http=fake)
    assert len(fake.calls) == 1
    url, headers, timeout = fake.calls[0]
    start, end = _search_window(alert_time, NOW)
    expected_query = urllib.parse.urlencode({
        "status": "success", "from": _iso(start), "to": _iso(end), "perPage": 100})
    assert url == "https://api.paystack.co/transaction?" + expected_query
    assert headers == {"Authorization": "Bearer " + key}
    assert timeout == 5
