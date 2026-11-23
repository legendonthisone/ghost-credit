"""Property test: hash format and value (fixed fake keys only)."""

from __future__ import annotations

import hashlib
import hmac
import re

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import hash_value

# Fake keys are made from pieces so no key-like literal sits in the repo.
_keys = st.text(min_size=1, max_size=30).map(lambda s: "fake" + "-key-" + s)


@settings(max_examples=100)
@given(st.text(max_size=40), _keys)
def test_hash_format_and_value(value: str, key: str) -> None:
    """Feature: pattern-network-hook, Property 11: Hash format and value.

    **Validates: Requirements 6.1, 6.2**
    """
    result = hash_value(value, key)
    assert result is not None
    assert len(result) == 69
    assert re.fullmatch(r"hmac:[0-9a-f]{64}", result)
    expected = hmac.new(key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()
    assert result == "hmac:" + expected


@settings(max_examples=100)
@given(st.text(max_size=20), _keys)
def test_missing_inputs_give_none(value: str, key: str) -> None:
    """Feature: pattern-network-hook, Property 11: missing value or key gives None.

    **Validates: Requirements 6.3, 6.4**
    """
    assert hash_value(None, key) is None
    assert hash_value(value, None) is None
    assert hash_value(value, "") is None
