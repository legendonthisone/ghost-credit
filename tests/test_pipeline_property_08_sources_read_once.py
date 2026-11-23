"""Feature: check-pipeline, Property 8: Sources are read once when, and only when, usable."""

from __future__ import annotations

from unittest import mock

from hypothesis import given, settings

from ghost_credit import pipeline
from ghost_credit.pipeline import FALLBACK_REASON, run_check
from ghost_credit.verdict import CHECK_REMINDER
from pipeline_fakes import (
    FakePaystack,
    RecordingNetwork,
    RecordingReader,
    TextExplainer,
    image_inputs,
    nows,
    sender_ids,
    texts,
)


@settings(max_examples=100, deadline=None)
@given(text=texts, sender=sender_ids, image=image_inputs, now=nows)
def test_sources_read_once_when_usable(text, sender, image, now) -> None:
    """**Validates: Requirements 2.1, 2.2, 2.9**"""
    text_ok = isinstance(text, str) and bool(text.strip())
    image_ok = isinstance(image, bytes) and len(image) > 0
    reader = RecordingReader()
    paystack = FakePaystack(raises=True)
    network = RecordingNetwork()
    explainer = TextExplainer()
    with mock.patch.object(
        pipeline, "parse_sms_alert", wraps=pipeline.parse_sms_alert
    ) as parser:
        result = run_check(
            text, sender, image, "spa", now,
            reader=reader, paystack_verify=paystack, network=network, explainer=explainer,
        )
    assert parser.call_count == (1 if text_ok else 0)
    assert len(reader.calls) == (1 if image_ok else 0)
    if not (text_ok or image_ok):
        assert result.reply == FALLBACK_REASON + " " + CHECK_REMINDER
        assert result.verdict.code == "UNVERIFIED"
        assert paystack.calls == []
        assert network.lookups == []
        assert network.reports == []
        assert explainer.calls == 0
