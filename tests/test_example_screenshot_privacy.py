"""Screenshots are read in memory only: no disk writes, no logs, no retention.

Validates: Requirements 8.2, 8.3, 8.4. Uses a synthetic image only.
"""

from __future__ import annotations

import base64
import builtins
import io
import json
import logging
import tempfile
from typing import Any

import pytest
from PIL import Image

from ghost_credit import FakeScreenshotReader

RESPONSE = {
    "amount_kobo": 5000000,
    "currency": "NGN",
    "narration": "synthetic-narration-marker-xyz",
}


def _png_bytes() -> bytes:
    """Make a small synthetic PNG in memory."""
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (10, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _refuse(*args: Any, **kwargs: Any) -> None:
    raise AssertionError("disk access is not allowed while reading")


def test_read_writes_no_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reading a valid image never opens a file or makes a temp file."""
    reader = FakeScreenshotReader(json.dumps(RESPONSE))
    image = _png_bytes()
    with monkeypatch.context() as m:
        m.setattr(builtins, "open", _refuse)
        m.setattr(tempfile, "NamedTemporaryFile", _refuse)
        m.setattr(tempfile, "TemporaryFile", _refuse)
        m.setattr(tempfile, "SpooledTemporaryFile", _refuse)
        m.setattr(tempfile, "mkstemp", _refuse)
        m.setattr(tempfile, "mkdtemp", _refuse)
        alert = reader.read(image)
    assert alert.amount_kobo == 5000000
    assert alert.screenshot_phash is not None


def test_read_logs_nothing_sensitive(caplog: pytest.LogCaptureFixture) -> None:
    """No log line holds image bytes, base64 of them, or the recorded reply."""
    image = _png_bytes()
    response_text = json.dumps(RESPONSE)
    reader = FakeScreenshotReader(response_text)
    with caplog.at_level(logging.DEBUG):
        reader.read(image)
    logged = caplog.text
    assert base64.b64encode(image).decode() not in logged
    assert repr(image) not in logged
    assert response_text not in logged
    assert "synthetic-narration-marker-xyz" not in logged


def _holds_image(value: object, image: bytes, depth: int = 0) -> bool:
    """Return True if value is, or directly contains, the image bytes."""
    if value == image:
        return True
    if depth > 3:
        return False
    if isinstance(value, dict):
        return any(_holds_image(v, image, depth + 1) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_holds_image(v, image, depth + 1) for v in value)
    return False


def test_result_and_reader_keep_no_image_bytes() -> None:
    """Neither the returned alert nor the reader holds the image."""
    image = _png_bytes()
    reader = FakeScreenshotReader(RESPONSE)
    alert = reader.read(image)
    assert not _holds_image(vars(alert), image)
    assert not _holds_image(vars(reader), image)
    assert not any(isinstance(v, (bytes, bytearray)) for v in vars(alert).values())
    assert not any(isinstance(v, (bytes, bytearray)) for v in vars(reader).values())
