"""Example tests for TRANSFER_REQUEST_WORDING (synthetic alerts only)."""
from ghost_credit.parser import parse_sms_alert

FLAG = "TRANSFER_REQUEST_WORDING"


def _flags(text: str, sender: str = "GTBank") -> list[str]:
    return parse_sms_alert(text, sender).red_flags


def test_fake_receipt_with_request_wording_is_flagged():
    """**Validates: Requirements 10.14, 11.1**"""
    text = (
        "Transfer Request Successful\n"
        "Amount: NGN45,000.00\n"
        "To account: 012****789"
    )
    assert _flags(text) == ["BALANCE_LINE_MISSING", FLAG]


def test_normal_credit_alert_is_not_flagged():
    """**Validates: Requirements 10.14, 11.8**"""
    text = (
        "Credit Alert: NGN45,000.00 received in acct 012****789.\n"
        "Narration: Payment for goods\n"
        "Avail Bal: NGN120,000.00"
    )
    assert _flags(text) == []


def test_odd_whitespace_and_curly_quotes_still_flag():
    """**Validates: Requirements 10.14, 11.3**"""
    assert FLAG in _flags("TRANSFER   request\tSUCCESSFUL")
    assert FLAG in _flags("\u201cTransfer request has been\u201d sent")


def test_words_near_each_other_flag_but_far_apart_do_not():
    """**Validates: Requirements 11.2, 11.4**"""
    # Whitespace runs collapse, so the gap is made of filler letters.
    near = "transfer " + "a" * 38 + " request successful"  # 40 characters between
    far = "transfer " + "a" * 39 + " request successful"  # 41 characters between
    assert FLAG in _flags(near)
    assert FLAG not in _flags(far)


def test_longer_words_and_empty_text_do_not_match():
    """**Validates: Requirements 11.5, 11.6**"""
    assert FLAG not in _flags("transferred request successful transfers")
    assert _flags("") == ["BALANCE_LINE_MISSING"]
    assert FLAG not in _flags("   \n\t ")


def test_flag_ignores_sender_id():
    """**Validates: Requirements 11.8**"""
    text = "Transfer Request Successful"
    assert FLAG in _flags(text, "+2348012345678")
    assert FLAG in _flags(text, None)
