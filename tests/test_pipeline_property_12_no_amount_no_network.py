"""Feature: check-pipeline, Property 12: No amount means no network traffic."""

from __future__ import annotations

from unittest import mock

from hypothesis import given, settings, strategies as st

from ghost_credit import pipeline
from ghost_credit.parser import ParsedAlert
from ghost_credit.pipeline import run_check
from pipeline_fakes import (
    FakePaystack,
    RecordingNetwork,
    RecordingReader,
    flag_lists,
    nows,
    paystack_results,
)

NO_AMOUNT_TEXTS = st.one_of(st.none(), st.just("hello there"), st.just("just words"))


def _lookup_seen_by_engine(calls: list) -> object:
    """Return the LookupResult the engine received (third argument)."""
    return calls[0].args[2]


@settings(max_examples=100)
@given(flags=flag_lists, text=NO_AMOUNT_TEXTS, now=nows, paystack=paystack_results())
def test_no_amount_means_empty_lookup_and_no_traffic(flags, text, now, paystack) -> None:
    """**Validates: Requirements 4.8, 4.9**"""
    network = RecordingNetwork()
    reader = RecordingReader(ParsedAlert(red_flags=list(flags)))
    with mock.patch.object(
        pipeline, "decide_with_notes", wraps=pipeline.decide_with_notes
    ) as engine:
        run_check(
            text, None, b"image", "spa", now,
            reader=reader, paystack_verify=FakePaystack(paystack), network=network,
        )
    lookup = _lookup_seen_by_engine(engine.call_args_list)
    assert network.lookups == []
    assert network.reports == []
    assert lookup.network_available is False
    assert lookup.matched is False
    assert lookup.matches == []


@settings(max_examples=100)
@given(flags=flag_lists, now=nows)
def test_builder_failure_means_empty_lookup_and_no_traffic(flags, now) -> None:
    """**Validates: Requirements 4.8, 4.9**"""
    network = RecordingNetwork()
    reader = RecordingReader(ParsedAlert(amount_kobo=4500000, red_flags=list(flags)))
    with mock.patch.object(pipeline, "build_signals", side_effect=ValueError("boom")):
        with mock.patch.object(
            pipeline, "decide_with_notes", wraps=pipeline.decide_with_notes
        ) as engine:
            run_check(
                None, None, b"image", "spa", now,
                reader=reader, paystack_verify=FakePaystack(raises=True), network=network,
            )
    lookup = _lookup_seen_by_engine(engine.call_args_list)
    assert network.lookups == []
    assert network.reports == []
    assert lookup.network_available is False
    assert lookup.matched is False
    assert lookup.matches == []
