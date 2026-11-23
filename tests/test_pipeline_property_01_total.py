"""Feature: check-pipeline, Property 1: Run_Check is total and returns a valid result."""

from __future__ import annotations

import uuid

from hypothesis import given, settings, strategies as st

from ghost_credit.pipeline import CheckResult, run_check
from pipeline_fakes import (
    FakePaystack,
    JunkExplainer,
    RaisingExplainer,
    RecordingNetwork,
    RecordingReader,
    TextExplainer,
    any_nows,
    categories,
    image_inputs,
    modes,
    parsed_alerts,
    paystack_results,
    sender_ids,
    texts,
)

CODES = {"CONFIRMED", "NOT_FOUND", "SUSPICIOUS", "UNVERIFIED"}
paystack_behaviour = st.one_of(
    paystack_results(),
    st.just("raise"),
    st.just("junk"),
)


def _make_paystack(choice: object) -> FakePaystack:
    """Turn a drawn choice into a fake Paystack callable."""
    if choice == "raise":
        return FakePaystack(raises=True)
    if choice == "junk":
        return FakePaystack({"status": "CONFIRMED"})
    return FakePaystack(choice)


@settings(max_examples=100, deadline=None)
@given(
    text=texts,
    sender=sender_ids,
    image=image_inputs,
    category=categories,
    now=any_nows,
    reader_alert=parsed_alerts,
    reader_mode=modes,
    paystack=paystack_behaviour,
    lookup_raises=st.booleans(),
    report_raises=st.booleans(),
    explainer=st.sampled_from([TextExplainer, JunkExplainer, RaisingExplainer]),
)
def test_run_check_is_total(
    text, sender, image, category, now, reader_alert, reader_mode,
    paystack, lookup_raises, report_raises, explainer,
) -> None:
    """**Validates: Requirements 1.2, 1.3, 7.1, 7.2, 9.2**"""
    result = run_check(
        text, sender, image, category, now,
        reader=RecordingReader(reader_alert, reader_mode),
        paystack_verify=_make_paystack(paystack),
        network=RecordingNetwork(lookup_raises=lookup_raises, report_raises=report_raises),
        explainer=explainer(),
    )
    assert isinstance(result, CheckResult)
    assert uuid.UUID(result.check_id).version == 4
    assert result.verdict.code in CODES
    assert isinstance(result.reply, str)
