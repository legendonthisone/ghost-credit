from hypothesis import given, settings, strategies as st

from ghost_credit.parser import PRESSURE_PHRASES, parse_sms_alert

# Synthetic alert lines with no pressure phrase. Each line is kept whole so that
# inserting a phrase on its own line cannot split an amount, label or date.
BASE_LINES = [
    "Credit Alert",
    "Acct: 012****789",
    "Amt: NGN50,000.00 CR",
    "Bal: N120,500.00",
    "Desc: Transfer from a customer",
    "Ref: ABCD1234",
    "Date: 12/03/2026 10:15:30",
    "Amt: N100.555",
    "Dear customer, thank you for banking with us",
]

ASCII_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
WORD_CHARS = st.sampled_from(ASCII_LETTERS + "0123456789_")


@st.composite
def written_phrase(draw):
    """A Pressure_Phrase with random letter case and whitespace runs between words."""
    phrase = draw(st.sampled_from(PRESSURE_PHRASES))
    words = phrase.split(" ")
    out = []
    for i, word in enumerate(words):
        if i:
            out.append(draw(st.text(alphabet=" \t\r\n", min_size=1, max_size=4)))
        flips = draw(st.lists(st.booleans(), min_size=len(word), max_size=len(word)))
        out.append("".join(c.upper() if f else c for c, f in zip(word, flips)))
    return "".join(out)


base_lines = st.lists(st.sampled_from(BASE_LINES), max_size=6)


def _insert(lines, index, line):
    index = min(index, len(lines))
    return "\n".join(lines[:index] + [line] + lines[index:])


# Feature: alert-parser, Property 7: Pressure phrases
# **Validates: Requirements 8.1, 8.2, 8.3, 8.5, 8.6, 10.10**
@settings(max_examples=200)
@given(
    lines=base_lines,
    index=st.integers(0, 6),
    phrase=written_phrase(),
    lead=st.sampled_from(["", " ", "Note: ", "!!"]),
    trail=st.sampled_from(["", " ", ".", "!!"]),
    sender=st.sampled_from([None, "GTBank", "08012345678"]),
)
def test_whole_word_phrase_is_flagged_and_changes_nothing_else(
    lines, index, phrase, lead, trail, sender
):
    base = "\n".join(lines)
    with_phrase = _insert(lines, index, lead + phrase + trail)

    before = parse_sms_alert(base, sender).red_flags
    after = parse_sms_alert(with_phrase, sender).red_flags

    assert "PRESSURE_LANGUAGE" not in before
    assert "PRESSURE_LANGUAGE" in after
    assert after.count("PRESSURE_LANGUAGE") == 1
    assert [f for f in after if f != "PRESSURE_LANGUAGE"] == before


@settings(max_examples=200)
@given(
    lines=base_lines,
    index=st.integers(0, 6),
    phrase=written_phrase(),
    prefix=st.text(alphabet=WORD_CHARS, max_size=3),
    suffix=st.text(alphabet=WORD_CHARS, max_size=3),
)
def test_phrase_inside_longer_word_is_not_flagged(lines, index, phrase, prefix, suffix):
    if not prefix and not suffix:
        prefix = "x"
    text = _insert(lines, index, prefix + phrase + suffix)
    assert "PRESSURE_LANGUAGE" not in parse_sms_alert(text, None).red_flags
