"""Example test: the `50,000.00 CR` amount form (Requirements 10.1, 10.2, 2.6)."""

from ghost_credit.parser import parse_sms_alert

# Synthetic alert: invented layout, masked account, no real names or numbers.
ALERT = (
    "Acct: 012****789\n"
    "Amt: 50,000.00 CR\n"
    "Desc: TRF FROM SAMPLE PAYER\n"
    "Date: 12/03/2026 10:45\n"
    "Avail Bal: 120,500.00"
)


def test_cr_form_amount_is_5_000_000_kobo_with_no_currency():
    result = parse_sms_alert(ALERT, "SAMPLEBANK")

    assert result.amount_kobo == 5_000_000
    assert result.currency is None
