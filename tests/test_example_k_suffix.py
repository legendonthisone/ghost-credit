from ghost_credit.parser import parse_sms_alert


def test_ngn_space_k_suffix_parses_to_5_000_000_kobo():
    # Synthetic alert: invented bank sender name, masked account, no real people.
    text = (
        "Credit Alert! Amt: NGN 50k "
        "Acct: 012****789 "
        "Narration: Payment for goods "
        "Bal: N120,500.00"
    )
    result = parse_sms_alert(text, "TESTBANK")
    assert result.amount_kobo == 5_000_000
