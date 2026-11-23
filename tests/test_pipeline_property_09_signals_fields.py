"""Feature: check-pipeline, Property 9: Signals carry the merged alert and no payer data."""

from __future__ import annotations

from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.pipeline import LAGOS, run_check
from pipeline_fakes import (
    FakePaystack,
    RecordingNetwork,
    RecordingReader,
    SAMPLE_SMS,
    amount_alerts,
    categories,
    nows,
)

sms_inputs = st.one_of(st.none(), st.just(SAMPLE_SMS), st.just("hello there"), st.just("  "))


@settings(max_examples=100)
@given(image_alert=amount_alerts, text=sms_inputs, now=nows, category=categories)
def test_signals_match_merged_alert(image_alert, text, now, category) -> None:
    """**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**"""
    network = RecordingNetwork()
    result = run_check(
        text, "GTBank", b"image", category, now,
        reader=RecordingReader(image_alert),
        paystack_verify=FakePaystack(raises=True),
        network=network,
    )
    assert len(network.lookups) == 1
    signals = network.lookups[0]
    parsed = result.parsed

    assert signals.check_id == result.check_id
    assert signals.checked_at.endswith("+01:00")
    instant = now if now.tzinfo is not None else now.replace(tzinfo=LAGOS)
    assert datetime.fromisoformat(signals.checked_at) == instant.replace(microsecond=0)
    assert signals.amount_kobo == parsed.amount_kobo
    assert signals.claimed_bank == parsed.claimed_bank
    assert signals.sender_id == parsed.sender_id
    assert signals.claimed_reference == parsed.claimed_reference
    assert signals.screenshot_phash == parsed.screenshot_phash
    assert signals.red_flags == parsed.red_flags
    assert signals.currency == "NGN"
    assert signals.channel == ("sms" if isinstance(text, str) and text.strip() else "screenshot")
    assert signals.payer_name_hash is None
    assert signals.payer_account_hash is None
    assert signals.payer_phone_hash is None
