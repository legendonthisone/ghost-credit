"""Feature: check-pipeline, Property 6: Merge keeps text values first, fills gaps from the screenshot."""

from __future__ import annotations

import copy
import dataclasses

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import ParsedAlert
from ghost_credit.pipeline import merge_alerts
from pipeline_fakes import parsed_alerts, sender_ids

OTHER = ("red_flags", "sender_id", "screenshot_phash")


@settings(max_examples=100)
@given(
    text_alert=st.one_of(st.none(), parsed_alerts),
    image_alert=st.one_of(st.none(), parsed_alerts),
    sender_id=sender_ids,
)
def test_text_first_then_screenshot(text_alert, image_alert, sender_id) -> None:
    """**Validates: Requirements 2.3, 2.4, 2.5, 2.7, 2.8, 2.12, 9.4**"""
    text_before = copy.deepcopy(text_alert)
    image_before = copy.deepcopy(image_alert)

    merged = merge_alerts(text_alert, image_alert, sender_id)

    for item in dataclasses.fields(ParsedAlert):
        if item.name in OTHER:
            continue
        from_text = getattr(text_alert, item.name) if text_alert is not None else None
        from_image = getattr(image_alert, item.name) if image_alert is not None else None
        expected = from_text if from_text is not None else from_image
        assert getattr(merged, item.name) == expected
    expected_phash = image_alert.screenshot_phash if image_alert is not None else None
    assert merged.screenshot_phash == expected_phash
    assert merged.sender_id == (sender_id if isinstance(sender_id, str) else None)
    assert text_alert == text_before
    assert image_alert == image_before
    assert merged.red_flags is not getattr(text_alert, "red_flags", None)
    assert merged.red_flags is not getattr(image_alert, "red_flags", None)
