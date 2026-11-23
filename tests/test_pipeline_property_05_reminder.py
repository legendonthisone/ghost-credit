"""Feature: check-pipeline, Property 5: Replies for unconfirmed verdicts end with the reminder."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pipeline import run_check
from ghost_credit.verdict import CHECK_REMINDER
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


@settings(max_examples=100, deadline=None)
@given(
    text=texts,
    sender=sender_ids,
    image=image_inputs,
    category=categories,
    now=any_nows,
    reader_alert=parsed_alerts,
    reader_mode=modes,
    paystack=st.one_of(paystack_results(), st.none()),
    explainer=st.sampled_from([TextExplainer, JunkExplainer, RaisingExplainer]),
)
def test_unconfirmed_replies_end_with_reminder(
    text, sender, image, category, now, reader_alert, reader_mode, paystack, explainer
) -> None:
    """**Validates: Requirements 5.4, 7.4, 9.5**"""
    result = run_check(
        text, sender, image, category, now,
        reader=RecordingReader(reader_alert, reader_mode),
        paystack_verify=FakePaystack(paystack, raises=paystack is None),
        network=RecordingNetwork(),
        explainer=explainer(),
    )
    if result.verdict.code != "CONFIRMED":
        assert result.reply.endswith(CHECK_REMINDER)
