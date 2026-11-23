"""Examples: how a Paystack input maps to confirmed / no match / no check."""

from __future__ import annotations

import pytest

from ghost_credit.verdict import _paystack_state
from verdict_helpers import make_paystack


@pytest.mark.parametrize(
    "value",
    [
        make_paystack("NOT_FOUND", False),
        make_paystack("UNAVAILABLE", False),
        make_paystack("UNAVAILABLE", True),
        make_paystack("SOMETHING_ELSE", True),
        make_paystack("NOT_FOUND", 1),  # truthy junk is not exactly True
        None,
        "CONFIRMED",
        42,
        object(),
    ],
)
def test_no_check_cases(value: object) -> None:
    assert _paystack_state(value) == "no_check"


def test_not_found_checked_is_no_match() -> None:
    assert _paystack_state(make_paystack("NOT_FOUND", True)) == "no_match"


def test_confirmed_reads_status_only() -> None:
    assert _paystack_state(make_paystack("CONFIRMED", True)) == "confirmed"
    assert _paystack_state(make_paystack("CONFIRMED", False)) == "confirmed"
