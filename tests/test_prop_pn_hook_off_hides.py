"""Property test: with the hook off, key, merchant_ref and payer hashes are all hidden."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import build_signals, get_hmac_key, get_merchant_ref

from pn_env import FAKE_KEY, FAKE_MERCHANT_REF, hook_env

_not_on = st.one_of(
    st.none(),
    st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=10),
).filter(lambda v: v is None or v.strip().lower() != "on")
_raw = st.none() | st.text(max_size=20)


@settings(max_examples=100)
@given(_not_on, _raw, _raw, _raw)
def test_hook_off_hides_everything(switch, name, account, phone) -> None:
    """Feature: pattern-network-hook, Property 5: Hook_Off hides secrets and hashes.
    **Validates: Requirements 3.7, 6.6**
    """
    with hook_env(switch=switch, key=FAKE_KEY, merchant_ref=FAKE_MERCHANT_REF):
        assert get_hmac_key() is None
        assert get_merchant_ref() is None
        s = build_signals(
            check_id="c1",
            checked_at="2026-11-20T10:40:05+01:00",
            channel="sms",
            amount_kobo=4500000,
            payer_name=name,
            payer_account=account,
            payer_phone=phone,
        )
        assert s.payer_name_hash is None
        assert s.payer_account_hash is None
        assert s.payer_phone_hash is None
        assert s.merchant_ref is None
