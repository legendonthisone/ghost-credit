"""Shared fakes for the WhatsApp webhook tests. Synthetic data only.

Nothing here touches the network, a file or an AI model. Fake secrets are
built from pieces so none of them looks like a real key.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from hypothesis import strategies as st

LAGOS = timezone(timedelta(hours=1))

# Distinctive fake secrets, built from pieces on purpose.
APP_SECRET = "fake-" + "app" + "-secret-" + "q7x2"
VERIFY_TOKEN = "fake-" + "verify" + "-token-" + "m4k9"
ACCESS_TOKEN = "fake-" + "access" + "-token-" + "z8w3"
PHONE_ID = "1234567890123"
SENDER = "2348000000001"
FIXED_NOW = datetime(2026, 11, 20, 10, 2, 11, tzinfo=LAGOS)
REPLY = "ALIVE. Release the goods."


def set_env(monkeypatch, **overrides: str | None) -> None:
    """Set the webhook environment with fake values; None removes a name."""
    values = {
        "WHATSAPP_VERIFY_TOKEN": VERIFY_TOKEN,
        "WHATSAPP_APP_SECRET": APP_SECRET,
        "WHATSAPP_TOKEN": ACCESS_TOKEN,
        "WHATSAPP_PHONE_NUMBER_ID": PHONE_ID,
        "MERCHANT_CATEGORY": None,
        "PATTERN_NETWORK": "off",
    }
    values.update(overrides)
    for name, value in values.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


@contextlib.contextmanager
def fake_env(**overrides: str | None):
    """Set the fake webhook environment for one block (safe inside Hypothesis)."""
    values = {
        "WHATSAPP_VERIFY_TOKEN": VERIFY_TOKEN,
        "WHATSAPP_APP_SECRET": APP_SECRET,
        "WHATSAPP_TOKEN": ACCESS_TOKEN,
        "WHATSAPP_PHONE_NUMBER_ID": PHONE_ID,
        "MERCHANT_CATEGORY": None,
        "PATTERN_NETWORK": "off",
    }
    values.update(overrides)
    saved = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def sign(body: bytes, secret: str = APP_SECRET) -> str:
    """Return the X-Hub-Signature-256 value for the body."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return "sha256=" + digest


def signed_headers(body: bytes, secret: str = APP_SECRET) -> dict[str, str]:
    """Return headers carrying a correct signature."""
    return {"X-Hub-Signature-256": sign(body, secret)}


def wrap_messages(messages: list[dict]) -> dict:
    """Wrap messages in the Cloud API envelope."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "0", "changes": [{"field": "messages",
                   "value": {"messaging_product": "whatsapp", "messages": messages}}]}],
    }


def text_message(body: str, sender: str = SENDER, message_id: str = "wamid.TEST1") -> dict:
    """Return one recorded-style text message."""
    return {"from": sender, "id": message_id, "timestamp": "1700000000",
            "type": "text", "text": {"body": body}}


def image_message(sender: str = SENDER, message_id: str = "wamid.IMG1") -> dict:
    """Return one recorded-style image message (no media is ever fetched)."""
    return {"from": sender, "id": message_id, "timestamp": "1700000000",
            "type": "image", "image": {"id": "media-1", "mime_type": "image/jpeg"}}


def status_payload() -> dict:
    """Return a delivery receipt payload with no messages."""
    return {"object": "whatsapp_business_account", "entry": [{"id": "0", "changes": [
        {"field": "messages", "value": {"messaging_product": "whatsapp",
         "statuses": [{"id": "wamid.X", "status": "delivered", "recipient_id": SENDER}]}}]}]}


def to_bytes(payload: object) -> bytes:
    """Encode a payload as JSON bytes."""
    return json.dumps(payload).encode("utf-8")


class RecordingSend:
    """A fake Send_Function that records calls and never touches the network."""

    def __init__(self, status: int = 200, raises: Exception | None = None) -> None:
        self.calls: list[tuple[str, dict, bytes, float]] = []
        self.status = status
        self.raises = raises

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        if self.raises is not None:
            raise self.raises
        return self.status, b"{}"

    def sent_bodies(self) -> list[dict]:
        """Return the decoded JSON bodies of every call."""
        return [json.loads(call[2]) for call in self.calls]


class FakeCheck:
    """A fake run_check: counts calls, records arguments, can raise per text."""

    def __init__(self, reply: str = REPLY, raise_for: set[str] | None = None) -> None:
        self.calls: list[tuple] = []
        self.kwargs: list[dict] = []
        self.reply = reply
        self.raise_for = raise_for or set()

    def __call__(self, text, sender_id, image_bytes, category, now, **kwargs):
        self.calls.append((text, sender_id, image_bytes, category, now))
        self.kwargs.append(kwargs)
        if text in self.raise_for:
            raise RuntimeError("fake check failure")
        return SimpleNamespace(reply=self.reply)


class FakeExplainer:
    """A stand-in explainer. The fake check never calls it."""

    def explain(self, *args, **kwargs):  # pragma: no cover - never called
        return "fake"


def fixed_clock() -> datetime:
    """Return the same Lagos time every time."""
    return FIXED_NOW


def post(body: bytes, *, headers: dict | None = None, **deps):
    """Call handle_webhook with POST and a correct signature unless headers given."""
    from ghost_credit.whatsapp import SeenSet, handle_webhook

    deps.setdefault("seen", SeenSet())
    deps.setdefault("clock", fixed_clock)
    return handle_webhook(
        "POST", {}, signed_headers(body) if headers is None else headers, body, **deps
    )


# --- Hypothesis strategies ---------------------------------------------------

senders = st.text(alphabet="0123456789", min_size=1, max_size=20)
message_ids = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789.=_-", min_size=1, max_size=40
).map(lambda s: "wamid." + s)
message_texts = st.text(max_size=300)
reply_texts = st.text(min_size=1, max_size=6000)
fake_secrets = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=12, max_size=24
).map(lambda s: "zz-fake-" + s)
header_values = st.dictionaries(
    st.text(max_size=20), st.one_of(st.text(max_size=80), st.none(), st.integers()), max_size=5
)
queries = st.one_of(
    st.none(),
    st.dictionaries(
        st.sampled_from(["hub.mode", "hub.verify_token", "hub.challenge", "x"]),
        st.one_of(st.text(max_size=30), st.none(), st.integers(), st.lists(st.text(max_size=3))),
        max_size=4,
    ),
)
arbitrary_bodies = st.one_of(
    st.none(), st.binary(max_size=400), st.text(max_size=400), st.integers(),
    st.just(b"{}"), st.just(b'{"entry": 5}'), st.just(b'{"entry":[{"changes":[{"value":{"messages":[1,"a",{}]}}]}]}'),
)
methods = st.one_of(st.sampled_from(["GET", "POST", "PUT", "get", "DELETE", ""]), st.none(), st.integers())
