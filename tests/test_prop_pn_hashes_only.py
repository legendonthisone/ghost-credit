"""Property test: with the hook on and a key, Signals hold hashes of normalised values only."""

from __future__ import annotations

from dataclasses import fields

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import (
    build_signals,
    hash_value,
    normalise_account,
    normalise_name,
    normalise_phone,
)

from pn_env import FAKE_KEY, FAKE_MERCHANT_REF, hook_env

_names = st.none() | st.text(alphabet="abcdefghijklmnopqrstuvwxyz .,'-", min_size=0, max_size=25)
_phones = st.none() | st.sampled_from(
    ["0803 123 4567", "+2348031234567", "2348031234567", "0803123", "abc", "(0803) 123-4567"]
)
_accounts = st.none() | st.sampled_from(
    ["0123456789", "0123 4567 89", "012****789", "12345", "01234abcde"]
)


@settings(max_examples=200)
@given(_names, _accounts, _phones)
def test_signals_carry_hashes_only(name, account, phone) -> None:
    """Feature: pattern-network-hook, Property 14: Hook_On Signals carry hashes only.
    **Validates: Requirements 6.5, 6.7, 6.9**
    """
    with hook_env(switch="on", key=FAKE_KEY, merchant_ref=FAKE_MERCHANT_REF):
        s = build_signals(
            check_id="c1",
            checked_at="2026-11-20T10:40:05+01:00",
            channel="sms",
            amount_kobo=4500000,
            payer_name=name,
            payer_account=account,
            payer_phone=phone,
        )
    assert s.payer_name_hash == hash_value(normalise_name(name), FAKE_KEY)
    assert s.payer_account_hash == hash_value(normalise_account(account), FAKE_KEY)
    assert s.payer_phone_hash == hash_value(normalise_phone(phone), FAKE_KEY)
    assert s.merchant_ref == FAKE_MERCHANT_REF
    # No raw payer value sits in any Signals field (only long, unmistakable raws are checked).
    raws = [r for r in (normalise_name(name), normalise_account(account), normalise_phone(phone)) if r and len(r) >= 6]
    for f in fields(s):
        value = getattr(s, f.name)
        if f.name in ("payer_name_hash", "payer_account_hash", "payer_phone_hash"):
            continue
        for raw in raws:
            assert raw not in str(value)
    for hashed in (s.payer_name_hash, s.payer_account_hash, s.payer_phone_hash):
        assert hashed is None or (hashed.startswith("hmac:") and len(hashed) == 69)
