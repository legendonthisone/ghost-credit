from hypothesis import given, settings, strategies as st

from ghost_credit.parser import parse_sms_alert

MAX_KOBO = 10**13


def _naira_kobo(kobo: int) -> tuple[int, int]:
    return kobo // 100, kobo % 100


def _fmt_n_comma(kobo: int) -> tuple[str, str | None]:
    naira, dd = _naira_kobo(kobo)
    return f"N{naira:,}.{dd:02d}", "NGN"


def _fmt_n_one_decimal(kobo: int) -> tuple[str, str | None]:
    # Only used for values with a zero second decimal digit.
    naira, dd = _naira_kobo(kobo)
    return f"N{naira:,}.{dd // 10}", "NGN"


def _fmt_ngn_plain(kobo: int) -> tuple[str, str | None]:
    return f"NGN{kobo // 100}", "NGN"


def _fmt_ngn_commas_space(kobo: int) -> tuple[str, str | None]:
    return f"NGN {kobo // 100:,}", "NGN"


def _fmt_ngn_k(kobo: int) -> tuple[str, str | None]:
    # kobo is a multiple of 100_000, so the k value is a whole number.
    return f"NGN {kobo // 100_000}k", "NGN"


def _fmt_ngn_k_decimal(kobo: int) -> tuple[str, str | None]:
    # kobo is a multiple of 10_000 (one decimal of k).
    tenths = kobo // 10_000
    return f"NGN {tenths // 10}.{tenths % 10}K", "NGN"


def _fmt_cr(kobo: int) -> tuple[str, str | None]:
    naira, dd = _naira_kobo(kobo)
    return f"{naira:,}.{dd:02d} CR", None


@st.composite
def amount_and_text(draw):
    """Draw (kobo, written amount, expected currency) in a random exact format."""
    kind = draw(
        st.sampled_from(
            ["n_comma", "n_one_decimal", "ngn_plain", "ngn_space", "ngn_k", "ngn_k_dec", "cr"]
        )
    )
    if kind in ("n_comma", "cr"):
        kobo = draw(st.integers(1, MAX_KOBO))
    elif kind == "n_one_decimal":
        kobo = draw(st.integers(1, MAX_KOBO // 10)) * 10
    elif kind in ("ngn_plain", "ngn_space"):
        kobo = draw(st.integers(1, MAX_KOBO // 100)) * 100
    elif kind == "ngn_k":
        kobo = draw(st.integers(1, MAX_KOBO // 100_000)) * 100_000
    else:
        kobo = draw(st.integers(1, MAX_KOBO // 10_000)) * 10_000
    fmt = {
        "n_comma": _fmt_n_comma,
        "n_one_decimal": _fmt_n_one_decimal,
        "ngn_plain": _fmt_ngn_plain,
        "ngn_space": _fmt_ngn_commas_space,
        "ngn_k": _fmt_ngn_k,
        "ngn_k_dec": _fmt_ngn_k_decimal,
        "cr": _fmt_cr,
    }[kind]
    written, currency = fmt(kobo)
    return kobo, written, currency


# Feature: alert-parser, Property 1: Amount round trip
# **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6, 2.7, 2.10, 6.5, 10.4**
@settings(max_examples=200)
@given(data=amount_and_text(), with_balance=st.booleans())
def test_amount_round_trip(data, with_balance):
    kobo, written, currency = data
    text = f"Credit Alert! Amt: {written} Acct: 012****789 Narration: Payment for goods"
    if with_balance:
        text += " Bal: N120,500.00"
    result = parse_sms_alert(text, "TESTBANK")
    assert result.amount_kobo == kobo, text
    assert result.currency == currency, text
    assert "AMOUNT_FORMAT_ODD" not in result.red_flags, text
