"""Property test: equal normalised values hash equal, different ones hash different."""

from __future__ import annotations

from hypothesis import assume, given, settings, strategies as st

from ghost_credit.pattern_network import (
    hash_value,
    normalise_account,
    normalise_name,
    normalise_phone,
)

_key = "fake" + "-key-" + "equality"
_digits10 = st.text(alphabet="0123456789", min_size=10, max_size=10)


@settings(max_examples=100)
@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ABCDE0123", min_size=1, max_size=30), st.sampled_from(["", " ", "  "]), st.sampled_from(["", ".", ","]))
def test_same_name_same_hash(base: str, pad: str, punct: str) -> None:
    """Feature: pattern-network-hook, Property 12: Hash equality (names).

    **Validates: Requirements 6.10**
    """
    a = normalise_name(base)
    b = normalise_name(pad + base.lower() + punct + pad)
    assume(a is not None)
    assert a == b
    assert hash_value(a, _key) == hash_value(b, _key)


@settings(max_examples=100)
@given(_digits10, _digits10)
def test_same_phone_and_account_same_hash(d1: str, d2: str) -> None:
    """Feature: pattern-network-hook, Property 12: Hash equality (phones, accounts).

    **Validates: Requirements 6.10**
    """
    p1, p2 = normalise_phone("0" + d1), normalise_phone("+234 " + d1)
    assert hash_value(p1, _key) == hash_value(p2, _key)
    a1, a2 = normalise_account(d2), normalise_account(d2[:5] + "-" + d2[5:])
    assert hash_value(a1, _key) == hash_value(a2, _key)


@settings(max_examples=100)
@given(st.text(max_size=30), st.text(max_size=30))
def test_different_values_different_hash(x: str, y: str) -> None:
    """Feature: pattern-network-hook, Property 12: Hash equality (different values).

    **Validates: Requirements 6.11**
    """
    assume(x != y)
    assert hash_value(x, _key) != hash_value(y, _key)
