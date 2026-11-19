from hypothesis import given, settings, strategies as st

from ghost_credit.parser import parse_sms_alert

_DIGITS = "0123456789"


@st.composite
def phone_senders(draw) -> str:
    prefix = draw(st.sampled_from(["0", "+234", "234"]))
    prefix_digits = len(prefix.lstrip("+"))
    total = draw(st.integers(min_value=7, max_value=15))
    rest = draw(
        st.lists(
            st.sampled_from(_DIGITS),
            min_size=total - prefix_digits,
            max_size=total - prefix_digits,
        )
    )
    # Optionally put a space or hyphen before each remaining digit.
    seps = draw(
        st.lists(
            st.sampled_from(["", "", " ", "-"]),
            min_size=len(rest),
            max_size=len(rest),
        )
    )
    return prefix + "".join(sep + digit for sep, digit in zip(seps, rest))


# Feature: alert-parser, Property 3: Phone-number senders are flagged
# **Validates: Requirements 4.1, 4.5, 4.6, 10.6**
@settings(max_examples=200)
@given(sender=phone_senders(), text=st.text(max_size=1000))
def test_phone_sender_always_flagged(sender: str, text: str) -> None:
    result = parse_sms_alert(text, sender)
    assert result.red_flags.count("SENDER_ID_MISMATCH") == 1
