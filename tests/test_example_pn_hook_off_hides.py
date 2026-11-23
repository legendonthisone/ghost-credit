"""Example tests: the hook off hides the key and merchant_ref even when both are set."""

from __future__ import annotations

from ghost_credit.pattern_network import (
    NoopPatternNetwork,
    build_signals,
    get_hmac_key,
    get_merchant_ref,
    get_network,
    is_hook_on,
)

from pn_env import FAKE_KEY, FAKE_MERCHANT_REF, hook_env


def test_unset_switch_hides_key_and_merchant_ref() -> None:
    with hook_env(switch=None, key=FAKE_KEY, merchant_ref=FAKE_MERCHANT_REF):
        assert not is_hook_on()
        assert get_hmac_key() is None
        assert get_merchant_ref() is None


def test_off_switch_hides_key_and_merchant_ref() -> None:
    with hook_env(switch="off", key=FAKE_KEY, merchant_ref=FAKE_MERCHANT_REF):
        assert get_hmac_key() is None
        assert get_merchant_ref() is None


def test_on_switch_returns_both() -> None:
    with hook_env(switch=" ON ", key=FAKE_KEY, merchant_ref=FAKE_MERCHANT_REF):
        assert get_hmac_key() == FAKE_KEY
        assert get_merchant_ref() == FAKE_MERCHANT_REF


def test_empty_key_counts_as_no_key() -> None:
    with hook_env(switch="on", key="", merchant_ref=""):
        assert get_hmac_key() is None
        assert get_merchant_ref() is None


def test_network_is_always_noop() -> None:
    for switch in (None, "off", "on"):
        with hook_env(switch=switch, key=FAKE_KEY):
            assert type(get_network()) is NoopPatternNetwork


def test_build_signals_defaults_and_phash() -> None:
    with hook_env():
        s = build_signals(
            check_id="c1",
            checked_at="2026-11-20T10:40:05+01:00",
            channel="screenshot",
            amount_kobo=4500000,
            screenshot_phash="phash:c3a1f0e2b4d69788",
            red_flags=("BALANCE_LINE_MISSING",),
            payer_name="Ada Test",
        )
    assert s.currency == "NGN"
    assert s.merchant_category == "other"
    assert s.screenshot_phash == "phash:c3a1f0e2b4d69788"
    assert s.red_flags == ["BALANCE_LINE_MISSING"]
    assert s.payer_name_hash is None and s.merchant_ref is None
