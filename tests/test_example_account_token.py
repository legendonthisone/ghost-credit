from ghost_credit.parser import parse_sms_alert


def test_account_number_is_not_read_as_amount() -> None:
    """The amount comes from the value after Amt, never from the account token."""
    result = parse_sms_alert("Acct:012****789 CR Amt: NGN 45,000.00", "GTBank")
    assert result.amount_kobo == 4500000
    assert result.currency == "NGN"
