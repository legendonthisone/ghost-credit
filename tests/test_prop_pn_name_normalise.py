"""Property test: name normalisation is idempotent and well formed."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import normalise_name


@settings(max_examples=200)
@given(st.text(max_size=40))
def test_name_normalisation(raw: str) -> None:
    """Feature: pattern-network-hook, Property 7: Name normalisation.

    **Validates: Requirements 5.1, 5.2, 5.8**
    """
    once = normalise_name(raw)
    assert normalise_name(once) == once
    if once is None:
        return
    assert once == once.upper()
    assert all(ch.isalnum() or ch == " " for ch in once)
    assert "  " not in once
    assert once == once.strip()


@settings(max_examples=100)
@given(st.text(alphabet=" \t\n.,;:!?-_()'\"*#@", max_size=20))
def test_no_letters_or_digits_gives_none(raw: str) -> None:
    """Feature: pattern-network-hook, Property 7: Name normalisation (empty result).

    **Validates: Requirements 5.2**
    """
    assert normalise_name(raw) is None


def test_none_gives_none() -> None:
    assert normalise_name(None) is None
