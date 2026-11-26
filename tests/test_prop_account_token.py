from hypothesis import given, settings, strategies as st

from ghost_credit.parser import parse_sms_alert

# Feature: alert-parser, Property 10: Account line never changes the amount

AMOUNT_TEXTS = [
    "Amt: NGN 45,000.00",
    "Amount: N1,250.50",
    "Amt: 7,500.00",
    "NGN50,000 credited",
    "50,000.00 CR",
    "Amt: NGN 50k",
]

DIGITS = st.text(alphabet="0123456789", min_size=0, max_size=6)


@st.composite
def account_lines(draw) -> str:
    """An Account_Label in random case, optional colon, and digits around 1-6 asterisks."""
    label = draw(st.sampled_from(["Acct", "A/C", "Account"]))
    label = "".join(draw(st.sampled_from([c.lower(), c.upper()])) for c in label)
    colon = draw(st.sampled_from(["", ":", ": "]))
    stars = "*" * draw(st.integers(min_value=1, max_value=6))
    return f"{label}{colon}{draw(DIGITS)}{stars}{draw(DIGITS)}"


@settings(max_examples=200)
@given(
    account=account_lines(),
    amount_text=st.sampled_from(AMOUNT_TEXTS),
    separator=st.sampled_from([" ", "\n", " CR "]),
)
def test_account_line_never_changes_amount(account: str, amount_text: str, separator: str) -> None:
    """**Validates: Requirements 2.11, 2.14, 2.15, 10.17**"""
    alone = parse_sms_alert(amount_text, "GTBank")
    with_account = parse_sms_alert(account + separator + amount_text, "GTBank")
    assert with_account.amount_kobo == alone.amount_kobo
