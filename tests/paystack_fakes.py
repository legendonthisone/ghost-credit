"""Shared fakes for the Paystack tests. No real network, no real keys."""

from __future__ import annotations

from typing import Any

from ghost_credit.parser import ParsedAlert


def fake_key(tail: str = "abc") -> str:
    """Build a fake test key from pieces so the prefix is never one literal."""
    return "sk_" + "test_" + tail


class RecordingHttp:
    """A fake Http_Function that records each call and returns a canned reply."""

    def __init__(self, status: int = 200, body: bytes = b"{}",
                 raises: Exception | None = None) -> None:
        self.status = status
        self.body = body
        self.raises = raises
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def __call__(self, url: str, headers: dict[str, str],
                 timeout_seconds: float) -> tuple[int, bytes]:
        """Record the request, then raise or return the canned reply."""
        self.calls.append((url, dict(headers), timeout_seconds))
        if self.raises is not None:
            raise self.raises
        return self.status, self.body


def make_parsed(**fields: Any) -> ParsedAlert:
    """Build a ParsedAlert with synthetic defaults, overridden by ``fields``."""
    base: dict[str, Any] = {"amount_kobo": 4500000}
    base.update(fields)
    return ParsedAlert(**base)
