"""Example test: `NGN50,000` (no space) parses to 5,000,000 kobo."""

from ghost_credit.parser import parse_sms_alert


def test_ngn_no_space_amount_is_5_000_000_kobo():
    text = (
        "Acct: 012****789\n"
        "Credit Alert: NGN50,000 received.\n"
        "Narration: Payment for goods\n"
        "Date: 15/03/2026 10:15\n"
        "Bal: NGN120,500.00"
    )
    result = parse_sms_alert(text, "TESTBANK")

    assert result.amount_kobo == 5_000_000
