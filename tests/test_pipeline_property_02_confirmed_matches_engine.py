"""Feature: check-pipeline, Property 2: CONFIRMED matches the engine, and the result passes through."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import LookupResult
from ghost_credit.pipeline import run_check
from ghost_credit.verdict import decide_with_notes
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
    explainer=st.sampled_from([TextExplainer, JunkExplainer, RaisingExplainer]),
)
def test_confirmed_matches_engine(text, now, image_alert, use_image, paystack, lookup, explainer) -> None:
    """**Validates: Requirements 3.6, 3.7, 5.5, 9.3**"""
    network = RecordingNetwork(lookup=lookup)
    result = run_check(
        text, "GTBank", b"image" if use_image else None, "spa", now,
        reader=RecordingReader(image_alert),
        paystack_verify=FakePaystack(paystack),
        network=network,
        explainer=explainer(),
    )
    seen = network.lookups[0] if network.lookups else None
    expected_lookup = lookup if seen is not None else LookupResult(False, False, [])
    direct = decide_with_notes(result.parsed, paystack, expected_lookup, alert_text=text)

    assert (result.verdict.code == "CONFIRMED") == (direct.verdict.code == "CONFIRMED")
    if paystack.status != "CONFIRMED":
        assert result.verdict.code != "CONFIRMED"
    assert result.paystack_result is paystack
