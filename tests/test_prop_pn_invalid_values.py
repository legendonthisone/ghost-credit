"""Property test: invalid contract values raise a ValueError that names the field."""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import ReportReceipt, Signals, Verdict

_not_int = st.one_of(
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(max_size=10),
    st.none(),
    st.booleans(),
    st.lists(st.integers(), max_size=2),
)
_bad_code = st.text(max_size=12).filter(
    lambda s: s not in ("CONFIRMED", "NOT_FOUND", "SUSPICIOUS", "UNVERIFIED")
)
_bad_outcome = st.text(max_size=12).filter(lambda s: s not in ("unknown", "fake", "real"))
_bad_status = st.text(max_size=12).filter(lambda s: s not in ("disabled", "queued", "rejected"))


@settings(max_examples=100)
@given(_not_int)
def test_bad_amount(value) -> None:
    """Feature: pattern-network-hook, Property 3: Invalid values are rejected by name (amount_kobo).

    **Validates: Requirements 2.7**
    """
    with pytest.raises(ValueError, match="amount_kobo"):
        Signals(check_id="c", checked_at="t", channel="sms", amount_kobo=value)


@settings(max_examples=100)
@given(_bad_code)
def test_bad_code(code) -> None:
    """Feature: pattern-network-hook, Property 3: Invalid values are rejected by name (code).

    **Validates: Requirements 2.8**
    """
    with pytest.raises(ValueError, match="code"):
        Verdict(code=code, paystack_checked=False)


@settings(max_examples=100)
@given(_bad_outcome)
def test_bad_owner_outcome(outcome) -> None:
    """Feature: pattern-network-hook, Property 3: Invalid values are rejected by name (owner_outcome).

    **Validates: Requirements 2.9**
    """
    with pytest.raises(ValueError, match="owner_outcome"):
        Verdict(code="UNVERIFIED", paystack_checked=False, owner_outcome=outcome)


@settings(max_examples=100)
@given(_bad_status)
def test_bad_status(status) -> None:
    """Feature: pattern-network-hook, Property 3: Invalid values are rejected by name (status).

    **Validates: Requirements 2.10**
    """
    with pytest.raises(ValueError, match="status"):
        ReportReceipt(accepted=False, status=status)
