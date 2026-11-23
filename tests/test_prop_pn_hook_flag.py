"""Property test: the hook is on only when PATTERN_NETWORK, trimmed and lowercased, is 'on'."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import is_hook_on

from pn_env import hook_env

_values = st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=12)


@settings(max_examples=200)
@given(_values)
def test_hook_flag_parsing(value: str) -> None:
    """Feature: pattern-network-hook, Property 4: Hook flag parsing.
    **Validates: Requirements 3.2, 3.3, 3.4**
    """
    with hook_env(switch=value):
        assert is_hook_on() == (value.strip().lower() == "on")


@settings(max_examples=100)
@given(st.sampled_from(["on", "ON", " On ", "oN\t"]), st.text(alphabet=" \t", max_size=3))
def test_on_forms_are_on(value: str, pad: str) -> None:
    """Feature: pattern-network-hook, Property 4: Hook flag parsing (on forms).
    **Validates: Requirements 3.3**
    """
    with hook_env(switch=pad + value + pad):
        assert is_hook_on()


def test_unset_is_off() -> None:
    """Feature: pattern-network-hook, Property 4: Hook flag parsing (unset).
    **Validates: Requirements 3.2**
    """
    with hook_env():
        assert not is_hook_on()
