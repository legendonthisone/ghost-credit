"""Feature: check-pipeline, Property 11: Reports follow the verdict and reuse the lookup Signals."""

from __future__ import annotations

from unittest import mock

from hypothesis import given, settings, strategies as st

from ghost_credit import pipeline
from ghost_credit.pipeline import run_check
from pipeline_fakes import (
    FakePaystack,
    RecordingNetwork,
    RecordingReader,
    SAMPLE_SMS,
    TextExplainer,
    image_inputs,
    lookup_results,
    nows,
    parsed_alerts,
    paystack_results,
)

text_choices = st.sampled_from([None, SAMPLE_SMS, "hello there", "  "])


@settings(max_examples=100, deadline=None)
@given(
    text=text_choices,
    image=image_inputs,
    now=nows,
    image_alert=parsed_alerts,
    paystack=paystack_results(),
    lookup=lookup_results(),
)
def test_reports_follow_verdict(text, image, now, image_alert, paystack, lookup) -> None:
    """**Validates: Requirements 6.1, 6.2, 6.3, 6.6, 6.7**"""
    log: list[str] = []
    network = RecordingNetwork(lookup=lookup, log=log)
    explainer = TextExplainer(log=log)
    real = pipeline.safe_report

    def spy(net, verdict, signals):
        log.append("safe_report")
        thread = real(net, verdict, signals)
        if thread is not None:
            thread.join(2)
        return thread

    with mock.patch.object(pipeline, "safe_report", side_effect=spy) as report:
        result = run_check(
            text, "GTBank", image, "spa", now,
            reader=RecordingReader(image_alert),
            paystack_verify=FakePaystack(paystack),
            network=network,
            explainer=explainer,
        )
    built = len(network.lookups) == 1
    if built and result.verdict.code != "CONFIRMED":
        assert report.call_count == 1
        _, verdict, signals = report.call_args.args
        assert signals is network.lookups[0]
        assert signals.check_id == result.check_id
        assert verdict.owner_outcome == "unknown"
        assert log.index("explain") < log.index("safe_report")
    else:
        assert report.call_count == 0
