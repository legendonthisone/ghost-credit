"""Screenshot reader foundations.

A screenshot reader turns the bytes of a bank transfer screenshot into the same
``ParsedAlert`` that the SMS parser returns. This module holds the shared
limits, the reader interface and two tiny helpers. It makes no AI, network or
file calls.
"""

from __future__ import annotations

import io
import json
import warnings
from datetime import datetime
from typing import Protocol

from ghost_credit.parser import ParsedAlert

# Largest image we will try to decode. Bigger input is refused unread.
MAX_IMAGE_BYTES = 10_000_000

# Longest recorded model reply we will parse. Longer text is ignored.
MAX_MODEL_OUTPUT_CHARS = 20_000


class ScreenshotReader(Protocol):
    """Anything that can read a screenshot's bytes into a ParsedAlert."""

    def read(self, image_bytes: bytes) -> ParsedAlert:
        """Read one screenshot and return what could be extracted from it."""
        ...


def __getattr__(name: str) -> object:
    """Load ``Image`` and ``imagehash`` on first access, not at import time.

    Why: the Lambda zip holds no image libraries, but older code and tests
    still read ``screenshot.Image`` and ``screenshot.imagehash``.
    """
    if name == "Image":
        from PIL import Image

        return Image
    if name == "imagehash":
        import imagehash

        return imagehash
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _empty_alert() -> ParsedAlert:
    """Return an alert with nothing filled in, used when a read fails."""
    return ParsedAlert()


def _phash_only(phash: str) -> ParsedAlert:
    """Return an alert whose only value is the screenshot hash."""
    return ParsedAlert(screenshot_phash=phash)


def _compute_phash(image_bytes: object) -> str | None:
    """Return the screenshot's perceptual hash, or None if it cannot be read.

    Why: the hash lets the same forged image be matched later. Anything that is
    not non-empty bytes of a safe size, or does not decode as an image, gives
    None so one bad upload can never crash a check. Work stays in memory.
    """
    if not isinstance(image_bytes, bytes):
        return None
    if len(image_bytes) == 0 or len(image_bytes) > MAX_IMAGE_BYTES:
        return None
    try:
        # Imported here so the rest of the app loads without these libraries.
        import imagehash
        from PIL import Image

        with warnings.catch_warnings():
            # Treat a suspiciously huge image as a failure, not a warning.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image_bytes)) as img:
                return "phash:" + str(imagehash.phash(img))
    except Exception:
        return None


# Limits for text fields taken from a recorded model reply.
_MAX_SHORT_TEXT = 100
_MAX_NARRATION = 200


def _clean_kobo(value: object) -> int | None:
    """Keep a value only if it is a real non-negative integer (not a bool)."""
    if type(value) is int and value >= 0:
        return value
    return None


def _clean_short_text(value: object) -> str | None:
    """Keep a value only if it is a string of at most 100 characters."""
    if type(value) is str and len(value) <= _MAX_SHORT_TEXT:
        return value
    return None


def _clean_time(value: object) -> datetime | None:
    """Parse an ISO 8601 time and keep the written clock time, no timezone.

    Why: alert-parser stores naive times, so ``replace`` keeps the clock time
    as written, where ``astimezone`` would shift it.
    """
    if type(value) is not str:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _load_object(model_output: object) -> dict | None:
    """Turn untrusted recorded output into a dict, or None if unusable."""
    try:
        if isinstance(model_output, dict):
            model_output = json.dumps(model_output)
        if type(model_output) is not str:
            return None
        if len(model_output) > MAX_MODEL_OUTPUT_CHARS:
            return None
        data = json.loads(model_output)
    except (ValueError, TypeError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


def build_alert_from_response(model_output: object, phash: str | None) -> ParsedAlert:
    """Build a ParsedAlert from untrusted recorded JSON and a local hash.

    Why: the reply is data, never instructions. Only nine known keys are read,
    each value is checked, and anything bad becomes None. The reply can say
    whether the image looks edited, but it never sets other red flags, the
    sender or the verdict, and the hash always comes from the caller.
    """
    data = _load_object(model_output)
    if data is None:
        return ParsedAlert(screenshot_phash=phash)
    narration = data.get("narration")
    currency = data.get("currency")
    return ParsedAlert(
        amount_kobo=_clean_kobo(data.get("amount_kobo")),
        currency="NGN" if type(currency) is str and currency == "NGN" else None,
        claimed_bank=_clean_short_text(data.get("claimed_bank")),
        sender_id=None,
        account_masked=_clean_short_text(data.get("account_masked")),
        narration=narration[:_MAX_NARRATION] if type(narration) is str else None,
        alert_time=_clean_time(data.get("alert_time")),
        available_balance_kobo=_clean_kobo(data.get("available_balance_kobo")),
        claimed_reference=_clean_short_text(data.get("claimed_reference")),
        red_flags=["SCREENSHOT_EDIT_SIGNS"] if data.get("edit_signs") is True else [],
        screenshot_phash=phash,
    )


class FakeScreenshotReader:
    """A test reader that returns recorded JSON instead of calling any model.

    Why: everything downstream can be tested for free. The image is only used
    to compute the local hash, and it is never stored or logged.
    """

    def __init__(self, recorded_response: str | dict | None = None) -> None:
        """Remember the recorded reply (if any) to use for every read."""
        self._recorded_response = recorded_response

    def read(self, image_bytes: bytes) -> ParsedAlert:
        """Return the alert for one screenshot, never raising.

        Undecodable input gives an empty alert, even with a recorded reply.
        """
        alert = _empty_alert()
        try:
            phash = _compute_phash(image_bytes)
            if phash is None:
                return alert
            alert = _phash_only(phash)
            if self._recorded_response is None:
                return alert
            return build_alert_from_response(self._recorded_response, phash)
        except Exception:
            return alert


class VisionScreenshotReader:
    """Stub for the real vision reader. It always refuses to run.

    Why: no model is approved yet, so nothing can be spent by accident. Wiring
    a real model needs Ayobami's approval and a quoted cost.
    """

    def read(self, image_bytes: bytes) -> ParsedAlert:
        """Raise NotImplementedError and do nothing else."""
        raise NotImplementedError("vision model not approved yet")
