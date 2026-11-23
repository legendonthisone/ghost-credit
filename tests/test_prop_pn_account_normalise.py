"""Property test: account numbers need exactly 10 digits; anything else gives None."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import normalise_account

_digits10 = st.text(alphabet="0123456789", min_size=10, max_size=10)
_filler = st.sampled_from(["", " ", "-"])


@st.composite
def _written(draw) -> tuple:
    """Write 10 digits with optional spaces or hyphens between them."""
    digits = draw(_digits10)
    out = digits[0]
    for ch in digits[1:]:
        out += draw(_filler) + ch
    return digits, out


@settings(max_examples=200)
@given(_written())
def test_accepted_account(case) -> None:
    """Feature: pattern-network-hook, Property 10: Account normalisation (accepted).

    **Validates: Requirements 5.6, 5.10**
    """
    digits, written = case
    result = normalise_account(written)
    assert result == digits
    assert normalise_account(result) == result


_wrong_count = st.integers(min_value=0, max_value=20).filter(lambda n: n != 10)


@settings(max_examples=100)
@given(_wrong_count, st.data())
def test_wrong_length(count: int, data) -> None:
    """Feature: pattern-network-hook, Property 10: Account normalisation (wrong length).

    **Validates: Requirements 5.7**
    """
    digits = data.draw(st.text(alphabet="0123456789", min_size=count, max_size=count))
    assert normalise_account(digits) is None


@settings(max_examples=100)
@given(_digits10, st.integers(0, 9), st.sampled_from("*xXabc#"))
def test_masked_or_lettered(digits: str, pos: int, bad: str) -> None:
    """Feature: pattern-network-hook, Property 10: Account normalisation (masked or lettered).

    **Validates: Requirements 5.7**
    """
    assert normalise_account(digits[:pos] + bad + digits[pos + 1:]) is None


def test_none_gives_none() -> None:
    assert normalise_account(None) is None
