"""Feature: check-pipeline, Property 3: Dependency failures never produce CONFIRMED or an error."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.paystack import UNAVAILABLE
from ghost_credit.pipeline import run_check
from pipeline_fakes import (
    FakePaystack,
    RecordingNetwork,
    RecordingReader,
    SAMPLE_SMS,
    nows,
    parsed_alerts,
)

junk_values = st.one_of(
    st.none(), st.integers(), st.text(max_size=5), st.dictionaries(st.text(max_size=3), st.integers(), max_size=2)
)


@settings(max_examples=100, deadline=None)
@given(
    now=nows,
    image_alert=parsed_alerts,
    junk=junk_values,
    raises=st.booleans(),
    text=st.sampled_from([None, SAMPLE_SMS, "hello there"]),
)
def test_paystack_failure_continues_unavailable(now, image_alert, junk, raises, text) -> None:
    """**Validates: Requirements 3.8, 3.9, 5.5**"""
    paystack = FakePaystack(junk, raises=raises)
    result = run_check(
        text, "GTBank", b"image", "spa", now,
        reader=RecordingReader(image_alert),
        paystack_verify=paystack,
        network=RecordingNetwork(),
    )
    assert result.verdict.code != "CONFIRMED"
    assert result.paystack_result.status == UNAVAILABLE
    assert result.paystack_result.checked is False
