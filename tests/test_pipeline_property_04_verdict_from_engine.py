"""Feature: check-pipeline, Property 4: The verdict comes only from the engine (model-based)."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import LookupResult
from ghost_credit.pipeline import run_check
from ghost_credit.verdict import build_reply, decide_with_notes
from pipeline_fakes import (
    FakePaystack,
    JunkExplainer,
    RaisingExplainer,
    RecordingNetwork,
    RecordingReader,
    SAMPLE_SMS,
    TextExplainer,
    lookup_results,
    nows,
    parsed_alerts,
    paystack_results,
)

usable_texts = st.sampled_from([SAMPLE_SMS, "hello there", "Alert NGN 500 rider outside"])


@settings(max_examples=100, deadline=None)
@given(
    text=usable_texts,
    now=nows,
    image_alert=parsed_alerts,
    use_image=st.booleans(),
    paystack=paystack_results(),
    lookup=lookup_results(),
    explainer_cls=st.sampled_from([TextExplainer, JunkExplainer, RaisingExplainer]),
)
def test_verdict_notes_and_reply_match_engine(
    text, now, image_alert, use_image, paystack, lookup, explainer_cls
) -> None:
    """**Validates: Requirements 1.4, 1.5, 4.10, 5.1, 5.2, 5.3, 7.8**"""
    network = RecordingNetwork(lookup=lookup)
    result = run_check(
        text, "GTBank", b"image" if use_image else None, "spa", now,
        reader=RecordingReader(image_alert),
        paystack_verify=FakePaystack(paystack),
        network=network,
        explainer=explainer_cls(),
    )
    expected_lookup = lookup if network.lookups else LookupResult(False, False, [])
    decision = decide_with_notes(result.parsed, paystack, expected_lookup, alert_text=text)

    assert result.verdict == decision.verdict
    assert result.risk_notes == list(decision.risk_notes)
    assert result.reply == build_reply(
        decision.verdict, result.parsed, explainer_cls(), decision.risk_notes
    )
