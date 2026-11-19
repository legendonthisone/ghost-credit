"""Example test: a forged-looking alert that triggers several red flags."""

from ghost_credit.parser import parse_sms_alert


def test_multi_flag_alert_reports_every_expected_code():
    # Synthetic alert: phone-number sender, no balance line, pressure text,
    # and an impossible date (31 February).
    text = (
        "Credit Alert: NGN50,000.00 received in acct 012****789.\n"
        "Narration: Payment for goods\n"
        "Date: 31/02/2026 10:15\n"
        "Please release now, I am waiting."
    )
    result = parse_sms_alert(text, "+2348012345678")

    expected = {
        "SENDER_ID_MISMATCH",
        "BALANCE_LINE_MISSING",
        "PRESSURE_LANGUAGE",
        "DATE_ODD",
    }
    for code in expected:
        assert code in result.red_flags
    assert len(result.red_flags) == len(set(result.red_flags))
