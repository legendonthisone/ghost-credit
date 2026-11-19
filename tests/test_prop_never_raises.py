from hypothesis import given, settings, strategies as st

from ghost_credit.parser import RED_FLAG_CODES, parse_sms_alert


# Feature: alert-parser, Property 2: Totality, shape and determinism
# **Validates: Requirements 1.1, 1.2, 1.5, 1.6, 9.3, 9.4, 9.5, 10.5**
@settings(max_examples=200)
@given(
    text=st.text(max_size=1000),
    sender_id=st.none() | st.text(max_size=100),
)
def test_parser_never_raises(text, sender_id):
    result = parse_sms_alert(text, sender_id)

    assert result.sender_id == sender_id
    assert len(result.red_flags) == len(set(result.red_flags))
    assert set(result.red_flags) <= set(RED_FLAG_CODES)

    assert parse_sms_alert(text, sender_id) == result
