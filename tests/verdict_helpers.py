"""Shared strategies and builders for the verdict-engine tests (synthetic data only)."""

from __future__ import annotations

from typing import Any

from hypothesis import strategies as st

from ghost_credit.parser import ParsedAlert, RED_FLAG_CODES
from ghost_credit.paystack import CONFIRMED, NOT_FOUND, UNAVAILABLE, PaystackResult
from ghost_credit.pattern_network import LookupResult

KNOWN_FLAGS = list(RED_FLAG_CODES)


def make_parsed(**kwargs: Any) -> ParsedAlert:
    """Build a ParsedAlert with defaults; pass only the fields you care about."""
    return ParsedAlert(**kwargs)


def make_paystack(status: str, checked: bool = True) -> PaystackResult:
    """Build a fake PaystackResult with the given status and checked value."""
    return PaystackResult(status, checked, None, None, None, "synthetic")


def is_paystack_confirmed(value: object) -> bool:
    """Oracle: a real PaystackResult whose status is CONFIRMED."""
    return isinstance(value, PaystackResult) and value.status == CONFIRMED


def is_paystack_no_match(value: object) -> bool:
    """Oracle: a real PaystackResult that is NOT_FOUND and was checked."""
    return (
        isinstance(value, PaystackResult)
        and value.status == NOT_FOUND
        and value.checked is True
    )


def is_network_match(value: object) -> bool:
    """Oracle: a LookupResult that is available and matched."""
    return (
        isinstance(value, LookupResult)
        and value.network_available is True
        and value.matched is True
    )


# --- strategies -----------------------------------------------------------

flag_entries = st.one_of(
    st.sampled_from(KNOWN_FLAGS),
    st.text(max_size=300),
    st.text(min_size=100, max_size=400),
    st.integers(),
    st.none(),
)
red_flag_lists = st.lists(flag_entries, max_size=8)
known_flag_lists = st.lists(st.sampled_from(KNOWN_FLAGS), max_size=6)

confirmed_results = st.builds(make_paystack, st.just(CONFIRMED), st.booleans())
no_match_results = st.just(make_paystack(NOT_FOUND, True))
no_check_results = st.one_of(
    st.just(make_paystack(NOT_FOUND, False)),
    st.just(make_paystack(UNAVAILABLE, False)),
    st.builds(make_paystack, st.text(max_size=10).filter(lambda s: s != CONFIRMED
                                                        and s != NOT_FOUND),
              st.booleans()),
    st.none(),
    st.integers(),
    st.text(max_size=10),
    st.just(object()),
)
not_confirmed_results = st.one_of(no_match_results, no_check_results)
paystack_inputs = st.one_of(confirmed_results, not_confirmed_results)

lookup_results = st.one_of(
    st.builds(
        LookupResult,
        network_available=st.booleans(),
        matched=st.booleans(),
    ),
    st.none(),
    st.integers(),
    st.just(object()),
)

parsed_alerts = st.builds(
    ParsedAlert,
    amount_kobo=st.one_of(st.none(), st.integers(min_value=0, max_value=10**10)),
    red_flags=red_flag_lists,
)
