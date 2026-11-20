"""Tests that the vision reader stub refuses to run, with the exact message."""

import io

import pytest
from PIL import Image

from ghost_credit.screenshot import VisionScreenshotReader

MESSAGE = "vision model not approved yet"


def _png_bytes() -> bytes:
    """Build a tiny synthetic PNG in memory."""
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (200, 30, 90)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("payload", [b"anything", b"", _png_bytes()])
def test_vision_stub_raises_exact_message(payload: bytes) -> None:
    """Any input raises NotImplementedError with the exact message."""
    with pytest.raises(NotImplementedError) as info:
        VisionScreenshotReader().read(payload)
    assert str(info.value) == MESSAGE
