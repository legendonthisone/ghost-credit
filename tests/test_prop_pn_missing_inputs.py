"""Property test: a missing value or key gives no hash; hook on without a key hides payer hashes."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import build_signals, hash_value

from pn_env import hook_env

_raw = st.none() | st.text(max_size=20)


@settings(max_examples=100)
@given(st.text(max_size=20), st.text(min_size=1, max_size=20), st.sampled_from([None, ""]))
def test_none_value_or_empty_key(value: str, key: str, empty_key) -> None:
    """Feature: pattern-network-hook, Property 13: Missing inputs give None (hasher).
    **Validates: Requirements 6.3, 6.4**
    """
    assert hash_value(None, key) is None
    assert hash_value(value, empty_key) is None


@settings(max_examples=100)
@given(_raw, _raw, _raw, st.sampled_from([None, ""]))
def test_hook_on_without_key(name, account, phone, key) -> None:
    """Feature: pattern-network-hook, Property 13: Missing inputs give None (builder).
    **Validates: Requirements 6.8**
    """
    with hook_env(switch="on", key=key, merchant_ref=None):
        s = build_signals(
            check_id="c1",
            checked_at="2026-11-20T10:40:05+01:00",
            channel="sms",
            amount_kobo=100,
            payer_name=name,
            payer_account=account,
            payer_phone=phone,
        )
    assert s.payer_name_hash is None
    assert s.payer_account_hash is None
    assert s.payer_phone_hash is None
