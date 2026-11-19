from hypothesis import given, settings, strategies as st

from ghost_credit.parser import parse_sms_alert

LABELS = ["Bal", "Bal.", "Avail Bal", "Avail. Bal", "Available Balance", "Current Balance"]
SEPARATORS = ["", ":", "-", ": ", " : ", " "]
MARKERS = ["", "N", "NGN", "NGN ", "\u20a6"]

# Filler text without the letter "b", so it can never contain a Balance_Label.
_NO_B_ALPHABET = st.characters(blacklist_characters="bB", blacklist_categories=("Cs",))
filler = st.text(alphabet=_NO_B_ALPHABET, max_size=200)


@st.composite
def random_case(draw, value: str) -> str:
    flips = draw(st.lists(st.booleans(), min_size=len(value), max_size=len(value)))
    return "".join(c.swapcase() if flip else c for c, flip in zip(value, flips))


@st.composite
def figure(draw):
    """Draw (written figure, kobo) with thousands separators and 0 to 2 decimals."""
    kobo_whole = draw(st.integers(0, 10**11))
    decimals = draw(st.integers(0, 2))
    if decimals == 0:
        return f"{kobo_whole:,}", kobo_whole * 100
    frac = draw(st.integers(0, 10**decimals - 1))
    frac_text = f"{frac:0{decimals}d}"
    return f"{kobo_whole:,}.{frac_text}", kobo_whole * 100 + int(frac_text.ljust(2, "0"))


@st.composite
def balance_alert(draw):
    label = draw(random_case(draw(st.sampled_from(LABELS))))
    sep = draw(st.sampled_from(SEPARATORS))
    marker = draw(st.sampled_from(MARKERS))
    written, kobo = draw(figure())
    if not sep and marker[:1].isalpha():
        # "BalN0" reads as one word, not a label plus a marker, so keep a gap.
        sep = " "
    prefix = draw(filler) + " "
    suffix = " " + draw(filler)
    return f"{prefix}{label}{sep}{marker}{written}{suffix}", kobo


@st.composite
def label_without_figure(draw):
    """Text with a Balance_Label (any case) that is never followed by a figure."""
    label = draw(random_case(draw(st.sampled_from(LABELS))))
    tail = draw(st.sampled_from(["", ":", " -", ": pending", " unavailable", ": N"]))
    return draw(filler) + " " + label + tail


# Feature: alert-parser, Property 5: Balance line decides BALANCE_LINE_MISSING
# **Validates: Requirements 3.4, 5.1, 5.2, 5.3, 5.4, 5.5, 10.8**
@settings(max_examples=200)
@given(case=balance_alert(), sender=st.none() | st.text(max_size=20))
def test_balance_line_present(case, sender):
    text, kobo = case
    result = parse_sms_alert(text, sender)
    assert "BALANCE_LINE_MISSING" not in result.red_flags, text
    assert result.available_balance_kobo == kobo, text


@settings(max_examples=200)
@given(text=filler | label_without_figure(), sender=st.none() | st.text(max_size=20))
def test_balance_line_absent(text, sender):
    result = parse_sms_alert(text, sender)
    assert result.red_flags.count("BALANCE_LINE_MISSING") == 1, text
    assert result.available_balance_kobo is None, text
