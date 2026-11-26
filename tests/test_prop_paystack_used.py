"""Property tests for the already-used rule (Properties 16 and 17)."""

from __future__ import annotations

import json
from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import REASON_ALREADY_USED, verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
AMOUNT = 4500000

refs = st.text(alphabet="abcdef0123456789", min_size=1, max_size=12)


def _run(path: str, ref: str, is_used):
    """Run verify with one matching payment on the chosen path."""
    tx = {"status": "success", "currency": "NGN", "amount": AMOUNT, "reference": ref}
    data = tx if path == "reference" else [tx]
    fake = RecordingHttp(body=json.dumps({"data": data}).encode())
    parsed = make_parsed(claimed_reference=ref if path == "reference" else None)
    return verify(parsed, fake_key(), NOW, http=fake, is_used=is_used)


def _raises(reference: str) -> bool:
    raise RuntimeError("ledger broke")


bad_ledgers = st.sampled_from([
    lambda r: True,
    _raises,
    lambda r: None,
    lambda r: 1,
    lambda r: "yes",
    lambda r: 0,
])


# Feature: paystack-verifier, Property 16: A used or unverifiable reference is never confirmed
# **Validates: Requirements 10.3, 10.6, 10.7, 10.8, 10.9, 10.12**
@settings(max_examples=100, deadline=None)
@given(path=st.sampled_from(["reference", "search"]), ref=refs, is_used=bad_ledgers)
def test_used_or_unverifiable_never_confirmed(path, ref, is_used) -> None:
    result = _run(path, ref, is_used)
    assert result.status != "CONFIRMED"
    assert 0 < len(result.reason) <= 120
    if result.status == "NOT_FOUND":
        assert result.reason == REASON_ALREADY_USED
        assert result.checked is True and result.matched_reference == ref
    else:
        assert result.status == "UNAVAILABLE" and result.checked is False


# Feature: paystack-verifier, Property 17: An unused reference or no ledger changes nothing
# **Validates: Requirements 10.2, 10.4, 10.5, 10.10**
@settings(max_examples=100, deadline=None)
@given(path=st.sampled_from(["reference", "search"]), ref=refs)
def test_unused_or_no_ledger_changes_nothing(path, ref) -> None:
    plain = _run(path, ref, None)
    assert plain.status == "CONFIRMED"
    assert _run(path, ref, lambda r: False) == plain
