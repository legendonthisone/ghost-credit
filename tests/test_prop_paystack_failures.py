"""Property test: every Paystack failure gives UNAVAILABLE, never CONFIRMED."""

from __future__ import annotations

import json
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
tails = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=20)
amounts = st.integers(min_value=1, max_value=10**10)
refs = st.one_of(st.none(), st.just("GC-1001"))
errors = st.sampled_from([TimeoutError("slow"), OSError("down"), ValueError("x"),
                          RuntimeError("boom")])
bad_codes = st.integers(min_value=100, max_value=599).filter(lambda c: c != 200)
json_values = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=8)),
    lambda inner: st.one_of(st.lists(inner, max_size=3),
                            st.dictionaries(st.text(max_size=5), inner, max_size=3)),
    max_leaves=6)


def _bad_body(value: object, has_ref: bool) -> bytes | None:
    """Encode ``value`` as a body that verify must not be able to read, else None."""
    if isinstance(value, dict):
        wanted = dict if has_ref else list
        if isinstance(value.get("data"), wanted):
            return None
    return json.dumps(value).encode("utf-8")


bad_bytes = st.one_of(
    st.just(b""), st.just(b"not json"), st.just(b"\xff\xfe\x00"),
    st.binary(max_size=30).filter(lambda b: not _is_json(b)))


def _is_json(raw: bytes) -> bool:
    """True when the bytes decode as UTF-8 JSON."""
    try:
        json.loads(raw.decode("utf-8"))
        return True
    except ValueError:
        return False


class _WrongShape:
    """A fake Http_Function that returns something that is not (int, bytes)."""

    def __init__(self, value: object) -> None:
        self.value = value
        self.calls = 0

    def __call__(self, url, headers, timeout_seconds):
        self.calls += 1
        return self.value


def _assert_unavailable(result, reason: str) -> None:
    assert result.status == "UNAVAILABLE"
    assert result.checked is False
    assert result.reason == reason
    assert result.matched_reference is None
    assert result.amount_kobo is None
    assert result.paid_at is None


# Feature: paystack-verifier, Property 11: Failures give UNAVAILABLE and are not confirmed
# **Validates: Requirements 6.1, 6.2, 6.3**
@settings(max_examples=100)
@given(tail=tails, amount=amounts, ref=refs, error=errors)
def test_raise_is_unavailable(tail, amount, ref, error):
    fake = RecordingHttp(raises=error)
    result = verify(make_parsed(amount_kobo=amount, claimed_reference=ref),
                    fake_key(tail), NOW, http=fake)
    _assert_unavailable(result, "could not reach Paystack")
    assert len(fake.calls) == 1


# Feature: paystack-verifier, Property 11: wrong-shaped return value
# **Validates: Requirements 6.1**
@settings(max_examples=100)
@given(tail=tails, amount=amounts, ref=refs,
       value=st.one_of(st.none(), st.integers(), st.text(max_size=5),
                       st.just((200,)), st.just((1, 2, 3)), st.just(())))
def test_wrong_shape_is_unavailable(tail, amount, ref, value):
    fake = _WrongShape(value)
    result = verify(make_parsed(amount_kobo=amount, claimed_reference=ref),
                    fake_key(tail), NOW, http=fake)
    _assert_unavailable(result, "could not reach Paystack")
    assert fake.calls == 1


# Feature: paystack-verifier, Property 11: non-200 status
# **Validates: Requirements 6.2**
@settings(max_examples=100)
@given(tail=tails, amount=amounts, ref=refs, code=bad_codes,
       body=st.one_of(st.binary(max_size=30), st.just(b'{"data": []}')))
def test_non_200_is_unavailable(tail, amount, ref, code, body):
    fake = RecordingHttp(status=code, body=body)
    result = verify(make_parsed(amount_kobo=amount, claimed_reference=ref),
                    fake_key(tail), NOW, http=fake)
    _assert_unavailable(result, "Paystack did not answer normally")
    assert len(fake.calls) == 1


# Feature: paystack-verifier, Property 11: unreadable 200 body
# **Validates: Requirements 6.3**
@settings(max_examples=150)
@given(tail=tails, amount=amounts, has_ref=st.booleans(),
       body=st.one_of(bad_bytes, json_values.map(lambda v: v)))
def test_unreadable_body_is_unavailable(tail, amount, has_ref, body):
    if not isinstance(body, bytes):
        encoded = _bad_body(body, has_ref)
        if encoded is None:
            return
        body = encoded
    fake = RecordingHttp(status=200, body=body)
    ref = "GC-1001" if has_ref else None
    result = verify(make_parsed(amount_kobo=amount, claimed_reference=ref),
                    fake_key(tail), NOW, http=fake)
    _assert_unavailable(result, "Paystack reply could not be read")
