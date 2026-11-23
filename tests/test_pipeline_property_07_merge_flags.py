"""Feature: check-pipeline, Property 7: Merged red flags are the ordered union."""

from __future__ import annotations

from hypothesis import given, settings

from ghost_credit.parser import RED_FLAG_CODES, ParsedAlert
from ghost_credit.pipeline import FLAG_ORDER, merge_alerts
from pipeline_fakes import flag_lists


@settings(max_examples=100)
@given(first=flag_lists, second=flag_lists)
def test_flags_are_ordered_union(first, second) -> None:
    """**Validates: Requirements 2.6, 9.4**"""
    merged = merge_alerts(
        ParsedAlert(red_flags=list(first)), ParsedAlert(red_flags=list(second)), None
    ).red_flags

    assert set(merged) == set(first) | set(second)
    assert len(merged) == len(set(merged))
    known = [c for c in merged if c in FLAG_ORDER]
    others = [c for c in merged if c not in FLAG_ORDER]
    assert merged == known + others
    assert known == [c for c in FLAG_ORDER if c in merged]
    first_seen = [c for c in dict.fromkeys(list(first) + list(second)) if c not in FLAG_ORDER]
    assert others == first_seen
    for code in ("SCREENSHOT_EDIT_SIGNS", "TRANSFER_REQUEST_WORDING"):
        if code in first or code in second:
            assert code in merged


def test_flag_order_uses_the_parser_codes() -> None:
    """FLAG_ORDER is the parser's tuple, which now holds TRANSFER_REQUEST_WORDING last."""
    assert tuple(FLAG_ORDER) == tuple(RED_FLAG_CODES)
    assert FLAG_ORDER[-1] == "TRANSFER_REQUEST_WORDING"
