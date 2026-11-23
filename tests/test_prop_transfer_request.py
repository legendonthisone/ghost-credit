from hypothesis import given, settings, strategies as st

from ghost_credit.parser import TRANSFER_REQUEST_PHRASES, parse_sms_alert

CLEAN_LINES = [
    "Credit Alert: NGN45,000.00 received in acct 012****789.",
    "Narration: Payment for goods",
    "Avail Bal: NGN120,000.00",
]


@st.composite
def _phrase(draw):
    """A listed phrase with random letter case and whitespace runs."""
    words = draw(st.sampled_from(TRANSFER_REQUEST_PHRASES)).split()
    parts: list[str] = []
    for word in words:
        cased = "".join(
            ch.upper() if draw(st.booleans()) else ch for ch in word
        )
        parts.append(cased)
    gaps = [draw(st.text(alphabet=" \t", min_size=1, max_size=4)) for _ in parts[1:]]
    return parts[0] + "".join(g + p for g, p in zip(gaps, parts[1:]))


# Feature: alert-parser, Property 9: Transfer request phrase adds the flag exactly once
# **Validates: Requirements 11.1, 11.3, 11.7, 11.9, 10.15**
@settings(max_examples=200)
@given(phrase=_phrase(), index=st.integers(min_value=0, max_value=len(CLEAN_LINES)))
def test_transfer_request_phrase_adds_flag_exactly_once(phrase, index):
    clean = parse_sms_alert("\n".join(CLEAN_LINES), "GTBank").red_flags
    assert clean == []
    lines = CLEAN_LINES[:index] + [phrase] + CLEAN_LINES[index:]
    flags = parse_sms_alert("\n".join(lines), "GTBank").red_flags
    assert flags.count("TRANSFER_REQUEST_WORDING") == 1
    assert [f for f in flags if f != "TRANSFER_REQUEST_WORDING"] == clean
