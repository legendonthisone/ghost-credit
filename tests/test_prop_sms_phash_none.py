from hypothesis import given, settings, strategies as st

from ghost_credit.parser import RED_FLAG_CODES, parse_sms_alert


def test_red_flag_codes_order_and_new_last_entry():
    assert RED_FLAG_CODES[:5] == (
        "SENDER_ID_MISMATCH",
        "BALANCE_LINE_MISSING",
        "AMOUNT_FORMAT_ODD",
        "DATE_ODD",
        "PRESSURE_LANGUAGE",
    )
    assert RED_FLAG_CODES[-1] == "SCREENSHOT_EDIT_SIGNS"
    assert len(RED_FLAG_CODES) == 6


# Feature: screenshot-reader, Property 8: SMS parsing leaves the screenshot hash empty
# **Validates: Requirements 1.1, 1.2, 1.3**
@settings(max_examples=100)
@given(
    text=st.text(max_size=300),
    sender=st.one_of(st.none(), st.text(max_size=20)),
)
def test_sms_parsing_leaves_phash_none(text, sender):
    result = parse_sms_alert(text, sender)
    assert result.screenshot_phash is None
    assert "SCREENSHOT_EDIT_SIGNS" not in result.red_flags
