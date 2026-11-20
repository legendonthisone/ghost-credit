"""Property test: the screenshot hash matches the library and is stable."""
from __future__ import annotations

import io
import re

import imagehash
from hypothesis import given, settings, strategies as st
from PIL import Image

from ghost_credit.screenshot import _compute_phash


@st.composite
def small_png(draw: st.DrawFn) -> bytes:
    """Build a small synthetic PNG with a few random pixels, in memory."""
    w = draw(st.integers(8, 64))
    h = draw(st.integers(8, 64))
    colour = draw(st.tuples(*[st.integers(0, 255)] * 3))
    img = Image.new("RGB", (w, h), colour)
    for _ in range(draw(st.integers(0, 10))):
        xy = (draw(st.integers(0, w - 1)), draw(st.integers(0, h - 1)))
        img.putpixel(xy, draw(st.tuples(*[st.integers(0, 255)] * 3)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# Feature: screenshot-reader, Property 6: Perceptual hash matches the library and is stable
@settings(max_examples=100, deadline=None)
@given(data=small_png())
def test_prop_phash(data: bytes) -> None:
    """**Validates: Requirements 2.4, 4.1, 4.2, 4.3, 9.6**"""
    result = _compute_phash(data)
    expected = "phash:" + str(imagehash.phash(Image.open(io.BytesIO(data))))
    assert result == expected
    assert re.fullmatch(r"phash:[0-9a-f]{16}", result)
    assert _compute_phash(data) == result
