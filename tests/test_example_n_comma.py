"""Example test: `N50,000.00` parses to 5,000,000 kobo."""

from ghost_credit.parser import parse_sms_alert


def test_n_comma_decimal_amount_is_5_000_000_kobo():
    text = (
        "Acct: 012****789\n"
        "Credit Alert: N50,000.00 received.\n"
        "Narration: Payment for goods\n"
        "Date: 15/03/2026 10:15\n"
        "Bal: N120,500.00"
    )
    result = parse_sms_alert(text, "TESTBANK")

    assert result.amount_kobo == 5_000_000
    assert result.currency == "NGN"
