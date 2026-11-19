from ghost_credit.parser import parse_sms_alert


def test_date_without_time_is_not_odd():
    text = "Credit Alert! Amt: N5,000.00 Acct: 012****789 Date: 12/03/2026 Bal: N120,500.00"
    result = parse_sms_alert(text, "TESTBANK")
    assert result.alert_time is None
    assert "DATE_ODD" not in result.red_flags
