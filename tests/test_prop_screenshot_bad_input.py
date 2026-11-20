"""Bad input to _compute_phash returns None and never raises."""
from __future__ import annotations

import io

from hypothesis import given, settings, strategies as st
from PIL import Image

from ghost_credit import screenshot
from ghost_credit.screenshot import MAX_IMAGE_BYTES, _compute_phash


def _decodes(data: bytes) -> bool:
    """Say whether Pillow can fully decode these bytes (the oracle)."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
        return True
    except Exception:
        return False


# Feature: screenshot-reader, Property 7: Bad input gives an Empty_Alert (hash level)
@settings(max_examples=100, deadline=None)
@given(data=st.binary(max_size=2000))
def test_prop_bad_bytes(data: bytes) -> None:
    """**Validates: Requirements 7.1, 9.4**"""
    result = _compute_phash(data)
    if not _decodes(data):
        assert result is None


# Feature: screenshot-reader, Property 7: Bad input gives an Empty_Alert (hash level)
@settings(max_examples=100, deadline=None)
@given(
    value=st.one_of(
        st.none(), st.text(), st.integers(), st.lists(st.integers()),
        st.binary(max_size=50).map(bytearray),
    )
)
def test_prop_non_bytes(value: object) -> None:
    """**Validates: Requirements 7.2, 9.4**"""
    assert _compute_phash(value) is None


def test_oversize_never_decoded(monkeypatch) -> None:
    """10,000,001 bytes gives None and Image.open is never called."""
    calls: list[object] = []
    monkeypatch.setattr(
        screenshot.Image, "open", lambda *a, **k: calls.append(a)
    )
    assert _compute_phash(b"\x00" * (MAX_IMAGE_BYTES + 1)) is None
    assert calls == []
