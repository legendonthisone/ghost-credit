"""Property test: phones that are not an accepted form give None."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import normalise_phone

_prefix = st.sampled_from(["+234", "234", "0"])
_wrong_count = st.integers(min_value=0, max_value=25).filter(lambda n: n != 10)


@settings(max_examples=100)
@given(_prefix, _wrong_count, st.data())
def test_wrong_digit_count(prefix: str, count: int, data) -> None:
    """Feature: pattern-network-hook, Property 9: Invalid phones give None (wrong length).

    **Validates: Requirements 5.5**
    """
    digits = data.draw(st.text(alphabet="0123456789", min_size=count, max_size=count))
    assert normalise_phone(prefix + digits) is None


@settings(max_examples=100)
@given(_prefix, st.text(alphabet="0123456789", min_size=10, max_size=10), st.integers(0, 9),
       st.sampled_from("abcXYZ#*"))
def test_letters_or_symbols(prefix: str, digits: str, pos: int, bad: str) -> None:
    """Feature: pattern-network-hook, Property 9: Invalid phones give None (bad character).

    **Validates: Requirements 5.5**
    """
    broken = digits[:pos] + bad + digits[pos + 1:]
    assert normalise_phone(prefix + broken) is None


def test_none_gives_none() -> None:
    assert normalise_phone(None) is None
