"""Example tests for FakeScreenshotReader, using synthetic images only."""

import io
import json
import re
from datetime import datetime

from PIL import Image

from ghost_credit.parser import ParsedAlert
from ghost_credit.screenshot import FakeScreenshotReader

PHASH_FORMAT = re.compile(r"^phash:[0-9a-f]{16}$")

RECORDED = {
    "amount_kobo": 5000000,
    "currency": "NGN",
    "claimed_bank": "TestBank",
    "account_masked": "012****789",
    "narration": "Payment for goods",
    "alert_time": "2026-03-12T10:15:00",
    "available_balance_kobo": 12000000,
    "claimed_reference": "REF123456",
    "edit_signs": True,
}


def _png() -> bytes:
    """Make a small synthetic PNG in memory."""
    img = Image.new("RGB", (32, 32), (200, 30, 30))
    for x in range(8, 24):
        img.putpixel((x, 16), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_recorded_response_gives_validated_fields_and_phash():
    for recorded in (RECORDED, json.dumps(RECORDED)):
        alert = FakeScreenshotReader(recorded).read(_png())
        assert alert.amount_kobo == 5000000
        assert alert.currency == "NGN"
        assert alert.claimed_bank == "TestBank"
        assert alert.account_masked == "012****789"
        assert alert.narration == "Payment for goods"
        assert alert.alert_time == datetime(2026, 3, 12, 10, 15, 0)
        assert alert.available_balance_kobo == 12000000
        assert alert.claimed_reference == "REF123456"
        assert alert.sender_id is None
        assert alert.red_flags == ["SCREENSHOT_EDIT_SIGNS"]
        assert PHASH_FORMAT.match(alert.screenshot_phash)


def test_no_response_undecodable_bytes_gives_empty_alert():
    assert FakeScreenshotReader().read(b"not an image") == ParsedAlert()


def test_no_response_decodable_image_gives_phash_only_alert():
    alert = FakeScreenshotReader().read(_png())
    assert PHASH_FORMAT.match(alert.screenshot_phash)
    assert alert == ParsedAlert(screenshot_phash=alert.screenshot_phash)
    assert alert.red_flags == []


def test_undecodable_bytes_with_response_still_gives_empty_alert():
    alert = FakeScreenshotReader(RECORDED).read(b"not an image")
    assert alert == ParsedAlert()
    assert alert.screenshot_phash is None
