"""Property: a screenshot read by the vision reader never confirms by itself.

Whatever the model says, without a Paystack match the verdict is UNVERIFIED or
SUSPICIOUS (worse). Only a Paystack match can give CONFIRMED. A fake Bedrock
client supplies the model text, so no AWS call is made.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import NOT_FOUND, UNAVAILABLE, PaystackResult
from ghost_credit.pipeline import run_check
from ghost_credit.screenshot import VisionScreenshotReader
from ghost_credit.verdict import TemplateExplainer
from vision_fakes import FakeBedrock, png_payload

NOW = datetime(2026, 11, 20, 10, 5, 0, tzinfo=timezone(timedelta(hours=1)))

no_match_results = st.sampled_from(
    [
        PaystackResult(UNAVAILABLE, False, None, None, None, "no Paystack key set"),
        PaystackResult(UNAVAILABLE, True, None, None, None, "could not reach Paystack"),
        PaystackResult(NOT_FOUND, True, None, None, None, "Paystack has no matching payment"),
    ]
)

json_scalars = st.one_of(
    st.none(), st.booleans(), st.integers(-10**13, 10**13), st.floats(allow_nan=False),
    st.text(max_size=40),
    st.sampled_from(["45,000.00", "NGN 45,000.00", "₦5,000", "CONFIRMED", "NGN"]),
)
# Replies a hostile or confused model might give: valid objects with any keys
# (including verdict and flag keys), arbitrary text, and odd JSON.
model_replies = st.one_of(
    st.dictionaries(
        st.sampled_from(
            ["amount", "currency", "bank", "reference", "date_time", "available_balance",
             "verdict", "code", "red_flags", "sender_id", "edit_signs", "confirmed"]
        ),
        json_scalars | st.lists(json_scalars, max_size=3),
        max_size=10,
    ).map(json.dumps),
    st.text(max_size=200),
    st.just('{"verdict": "CONFIRMED", "amount": "1,000.00", "currency": "NGN"}'),
)


def _no_network_paystack(result: PaystackResult):
    """Return a Paystack callable that answers with a fixed no-match result."""

    def call(parsed: object, now: object) -> PaystackResult:
        return result

    return call


@settings(max_examples=200, deadline=None)
@given(model_replies, no_match_results)
def test_vision_read_alone_is_never_confirmed(reply: str, paystack: PaystackResult) -> None:
    """**Validates: Requirement 9.9** (a screenshot alone is at best UNVERIFIED)."""
    reader = VisionScreenshotReader(FakeBedrock(reply))
    result = run_check(
        "",
        None,
        png_payload(),
        "other",
        NOW,
        reader=reader,
        paystack_verify=_no_network_paystack(paystack),
        explainer=TemplateExplainer(),
    )
    if paystack.status == NOT_FOUND:
        assert result.verdict.code in ("NOT_FOUND", "SUSPICIOUS", "UNVERIFIED")
    else:
        assert result.verdict.code in ("SUSPICIOUS", "UNVERIFIED")
    assert result.verdict.code != "CONFIRMED"
    assert result.verdict.decided_by == "rules"
