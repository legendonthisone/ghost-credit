"""Shared fakes for the vision reader tests. Synthetic data only.

Nothing here calls AWS or Meta. The fake Bedrock client records the Converse
arguments and returns a prepared reply.
"""
from __future__ import annotations

import json
from typing import Any

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"

# A distinctive marker so a test can search logs and stores for leaked bytes.
MARKER = b"SYNTHETIC-PIXELS-7c1e"


def png_payload(extra: bytes = MARKER) -> bytes:
    """Return bytes that look like a PNG to the file type check."""
    return PNG_MAGIC + extra


def jpeg_payload(extra: bytes = MARKER) -> bytes:
    """Return bytes that look like a JPEG to the file type check."""
    return JPEG_MAGIC + extra


GOOD_REPLY = {
    "amount": "45,000.00",
    "currency": "NGN",
    "bank": "GTBank",
    "reference": "REF-SYN-001",
    "date_time": "2026-11-20T10:02:11",
    "available_balance": "120,000.00",
}


def converse_reply(text: str) -> dict:
    """Wrap model text in the shape Bedrock Converse returns."""
    return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}}}


class FakeBedrock:
    """A bedrock-runtime client double: records calls, returns or raises."""

    def __init__(self, reply: object = None, raises: Exception | None = None) -> None:
        """``reply`` is model text, a dict (sent as JSON) or a full response."""
        self.reply = reply
        self.raises = raises
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> Any:
        """Record the arguments, then raise or answer."""
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        if isinstance(self.reply, dict) and "output" in self.reply:
            return self.reply
        if isinstance(self.reply, (dict, list)):
            return converse_reply(json.dumps(self.reply))
        return converse_reply(str(self.reply))
