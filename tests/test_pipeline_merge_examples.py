"""Example tests for reading and merging the alert sources."""

from __future__ import annotations

from datetime import datetime

from ghost_credit.parser import ParsedAlert
from ghost_credit.pipeline import _read_image, merge_alerts, run_check
from pipeline_fakes import (
    FakePaystack,
    RecordingNetwork,
    RecordingReader,
    SAMPLE_BYTES,
    SAMPLE_SMS,
)

NOW = datetime(2026, 11, 20, 10, 5)


def test_text_and_screenshot_merge_with_known_values() -> None:
    """Text wins on shared fields, the screenshot fills gaps, phash comes from the screenshot."""
    text_alert = ParsedAlert(amount_kobo=100, claimed_bank="GTBank", red_flags=["DATE_ODD"])
    image_alert = ParsedAlert(
        amount_kobo=999,
        narration="from Amaka",
        screenshot_phash="phash:0123456789abcdef",
        red_flags=["SCREENSHOT_EDIT_SIGNS"],
    )
    merged = merge_alerts(text_alert, image_alert, "GTBank")
    assert merged.amount_kobo == 100
    assert merged.claimed_bank == "GTBank"
    assert merged.narration == "from Amaka"
    assert merged.screenshot_phash == "phash:0123456789abcdef"
    assert merged.sender_id == "GTBank"
    assert merged.red_flags == ["DATE_ODD", "SCREENSHOT_EDIT_SIGNS"]


def test_reader_that_raises_gives_empty_alert_and_check_continues() -> None:
    """A broken reader must not stop a check that also has usable text."""
    reader = RecordingReader(mode="raise")
    assert _read_image(reader, SAMPLE_BYTES) == ParsedAlert()
    result = run_check(
        SAMPLE_SMS, "GTBank", SAMPLE_BYTES, "spa", NOW,
        reader=reader, paystack_verify=FakePaystack(raises=True), network=RecordingNetwork(),
    )
    assert len(reader.calls) == 2
    assert result.parsed.amount_kobo == 4500000
    assert result.verdict.code == "UNVERIFIED"


def test_reader_that_returns_junk_gives_empty_alert() -> None:
    """A reader that returns a non-alert is treated as an empty alert."""
    reader = RecordingReader(mode="junk")
    assert _read_image(reader, SAMPLE_BYTES) == ParsedAlert()
    result = run_check(
        None, None, SAMPLE_BYTES, "spa", NOW,
        reader=reader, paystack_verify=FakePaystack(raises=True), network=RecordingNetwork(),
    )
    assert result.parsed == ParsedAlert()
    assert result.verdict.code == "UNVERIFIED"


def test_edit_signs_and_transfer_request_survive_the_merge() -> None:
    """Flags from the screenshot and from the text both reach the merged alert."""
    text_alert = ParsedAlert(red_flags=["TRANSFER_REQUEST_WORDING"])
    image_alert = ParsedAlert(red_flags=["SCREENSHOT_EDIT_SIGNS"])
    merged = merge_alerts(text_alert, image_alert, None)
    assert merged.red_flags == ["SCREENSHOT_EDIT_SIGNS", "TRANSFER_REQUEST_WORDING"]
    assert merge_alerts(image_alert, text_alert, None).red_flags == merged.red_flags
