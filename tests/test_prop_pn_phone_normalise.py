"""Property test: every accepted phone form gives the same +234 result."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import normalise_phone

_digits10 = st.text(alphabet="0123456789", min_size=10, max_size=10)
_prefix = st.sampled_from(["+234", "234", "0"])
_filler = st.sampled_from(["", " ", "-", "(", ")"])


@st.composite
def _written(draw) -> tuple:
    """Write 10 subscriber digits in one accepted form, with optional filler between characters."""
    digits = draw(_digits10)
    prefix = draw(_prefix)
    out = prefix
    for ch in digits:
        out += draw(_filler) + ch
    return digits, prefix, out


@settings(max_examples=200)
@given(_written())
def test_phone_forms(case) -> None:
    """Feature: pattern-network-hook, Property 8: Phone normalisation across accepted forms.

    **Validates: Requirements 5.3, 5.9, 5.11**
    """
    digits, _prefix_used, written = case
    result = normalise_phone(written)
    assert result == "+234" + digits
    assert normalise_phone(result) == result


@settings(max_examples=100)
@given(_digits10)
def test_three_forms_agree(digits: str) -> None:
    """Feature: pattern-network-hook, Property 8: the three forms give one value.

    **Validates: Requirements 5.11**
    """
    results = {normalise_phone(p + digits) for p in ("+234", "234", "0")}
    assert results == {"+234" + digits}
