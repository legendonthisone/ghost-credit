"""Feature: check-pipeline, Property 10: Merchant category is trimmed or defaults to "other"."""

from __future__ import annotations

from datetime import datetime

from hypothesis import given, settings

from ghost_credit.pipeline import run_check
from pipeline_fakes import (
    RecordingNetwork,
    RecordingReader,
    FakePaystack,
    alert_with_amount,
    categories,
)

NOW = datetime(2026, 11, 20, 10, 5)


@settings(max_examples=100)
@given(category=categories)
def test_category_is_trimmed_or_other(category) -> None:
    """**Validates: Requirements 4.6**"""
    network = RecordingNetwork()
    run_check(
        None,
        None,
        b"image",
        category,
        NOW,
        reader=RecordingReader(alert_with_amount()),
        paystack_verify=FakePaystack(raises=True),
        network=network,
    )
    expected = (
        category.strip() if isinstance(category, str) and category.strip() else "other"
    )
    assert len(network.lookups) == 1
    assert network.lookups[0].merchant_category == expected
