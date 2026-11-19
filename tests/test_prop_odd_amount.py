from hypothesis import given, settings, strategies as st

from ghost_credit.parser import parse_sms_alert

MARKERS = ["N", "NGN", "NGN ", "\u20a6"]
PREFIXES = ["Credit alert: ", "Acct 012****789 credited with ", "", "Amt: "]
# Optional Balance_Line before or after the odd amount. The odd amount is still
# the first amount outside a Balance_Line.
BALANCE_BEFORE = ["", "Avail Bal: N5,000.00 "]
BALANCE_AFTER = ["", " Bal: N120,500.00", " on 05/03/2026 10:15"]


def _grouped(n: int) -> str:
    return f"{n:,}"


@st.composite
def many_decimals(draw):
    """A well-grouped number with 3 or more decimal digits (Requirements 2.9, 6.2)."""
    whole = _grouped(draw(st.integers(0, 10**12)))
    frac = draw(st.text(alphabet="0123456789", min_size=3, max_size=8))
    return f"{whole}.{frac}"


@st.composite
def bad_comma_group(draw):
    """First group of 1 to 3 digits, then a comma group that is not exactly 3 digits (6.3)."""
    first = str(draw(st.integers(1, 999)))
    groups = draw(
        st.lists(st.text(alphabet="0123456789", min_size=1, max_size=6), min_size=1, max_size=3)
    )
    if all(len(g) == 3 for g in groups):
        groups[draw(st.integers(0, len(groups) - 1))] += "7"
    number = first + "".join("," + g for g in groups)
    if draw(st.booleans()):
        number += "." + draw(st.text(alphabet="0123456789", min_size=1, max_size=2))
    return number


@st.composite
def mixed_separators(draw):
    """Comma and full stop in the wrong roles, such as 1.234,56 (6.1)."""
    first = str(draw(st.integers(1, 999)))
    groups = ["{:03d}".format(draw(st.integers(0, 999))) for _ in range(draw(st.integers(1, 2)))]
    tail = draw(st.text(alphabet="0123456789", min_size=1, max_size=3))
    return first + "".join("." + g for g in groups) + "," + tail


odd_numbers = st.one_of(many_decimals(), bad_comma_group(), mixed_separators())


@st.composite
def odd_alert(draw):
    return (
        draw(st.sampled_from(PREFIXES))
        + draw(st.sampled_from(BALANCE_BEFORE))
        + draw(st.sampled_from(MARKERS))
        + draw(odd_numbers)
        + draw(st.sampled_from(BALANCE_AFTER))
    )


# Feature: alert-parser, Property 8: Odd amount formats
# **Validates: Requirements 2.9, 6.1, 6.2, 6.3, 6.6, 10.11**
@settings(max_examples=200)
@given(text=odd_alert(), sender=st.none() | st.text(max_size=20))
def test_odd_amount_formats(text, sender):
    result = parse_sms_alert(text, sender)
    assert result.amount_kobo is None, text
    assert result.red_flags.count("AMOUNT_FORMAT_ODD") == 1, text
