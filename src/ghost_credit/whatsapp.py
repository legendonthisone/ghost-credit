"""WhatsApp webhook: check a pasted bank SMS and reply on WhatsApp.

Meta's WhatsApp Cloud API calls ``handle_webhook``. The function proves the
call is from Meta (HMAC signature), runs the existing ``run_check`` pipeline on
the SMS text and sends the plain-English reply back with one outbound call.

Rules this module keeps:
- Standard library only. The outbound call uses ``urllib.request`` and can be
  replaced by an injected ``send`` function in tests.
- Text only. Images and other media are never downloaded or read. The owner is
  asked to paste the SMS text instead.
- A WhatsApp number is not an SMS sender id, so ``sender_id`` is always None.
- Before the signature passes, any failure gives a fixed 403 and nothing is
  processed. After it passes, every failure still gives 200 so Meta does not
  retry forever.
- Logs hold only fixed event names, exception type names, status codes and
  counts. Never message text, phone numbers or secrets.
- Dedupe is best effort. The seen-message set lives in memory, so it lasts only
  as long as one process or one Lambda container. A durable store needs
  Ayobami's approval.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import urllib.error
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from ghost_credit.pattern_network import get_network
from ghost_credit.pipeline import LAGOS, make_paystack_verify, run_check
from ghost_credit.screenshot import FakeScreenshotReader
from ghost_credit.verdict import TemplateExplainer

GRAPH_API_VERSION = "v21.0"
GRAPH_URL_TEMPLATE = "https://graph.facebook.com/{version}/{phone_number_id}/messages"
MAX_BODY_BYTES = 262_144
MAX_TEXT_CHARS = 2000
MAX_REPLY_CHARS = 4096
SEND_TIMEOUT_SECONDS = 5.0
SEEN_CAPACITY = 1000
USER_AGENT = "ghost-credit/0.1"
ASK_FOR_SMS_REPLY = (
    "I can only check the SMS text for now. "
    "Please copy the alert SMS from your bank and paste it here."
)

# Fixed response bodies. None of them can hold a secret or customer data.
BODY_OK = "ok"
BODY_FORBIDDEN = "forbidden"
BODY_TOO_LARGE = "payload too large"
BODY_NOT_ALLOWED = "method not allowed"

_MAX_ID_CHARS = 200
_MAX_RESPONSE_READ = 65_536
_SENDER_RE = re.compile(r"[0-9]{1,20}")
_PHONE_ID_RE = re.compile(r"[0-9]{1,32}")

_log = logging.getLogger("ghost_credit.whatsapp")

SendFunction = Callable[[str, dict, bytes, float], "tuple[int, bytes]"]


@dataclass(frozen=True)
class WebhookResponse:
    """What the webhook answers to the caller."""

    status: int
    body: str
    content_type: str = "text/plain"


@dataclass(frozen=True)
class IncomingMessage:
    """One validated message from Meta. ``kind`` is "text" or "other"."""

    message_id: str | None
    sender: str
    kind: str
    text: str | None


class SeenSet:
    """A bounded, thread-safe set of message ids. The oldest id goes first."""

    def __init__(self, capacity: int = SEEN_CAPACITY) -> None:
        """Create an empty set that holds at most ``capacity`` ids."""
        self._capacity = max(1, int(capacity))
        self._ids: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()

    def add_if_new(self, message_id: str) -> bool:
        """Remember the id and return True, or return False if already seen."""
        with self._lock:
            if message_id in self._ids:
                return False
            self._ids[message_id] = None
            while len(self._ids) > self._capacity:
                self._ids.popitem(last=False)
            return True

    def __len__(self) -> int:
        """Return how many ids are remembered."""
        with self._lock:
            return len(self._ids)

    def __contains__(self, message_id: object) -> bool:
        """Say whether the id is remembered."""
        with self._lock:
            return message_id in self._ids


# One set per process or Lambda container, used when none is injected.
_DEFAULT_SEEN = SeenSet()


# --- Small helpers ---------------------------------------------------------


def _log_event(event: str, detail: object = None) -> None:
    """Log a fixed event name plus at most a type name or a status code."""
    if detail is None:
        _log.warning("%s", event)
    else:
        _log.warning("%s %s", event, detail)


def _env(name: str) -> str:
    """Return the trimmed environment variable, or "" when unset."""
    value = os.environ.get(name)
    return value.strip() if isinstance(value, str) else ""


def _normalise_headers(headers: object) -> dict[str, str]:
    """Return headers with lowercase names, keeping only text pairs."""
    result: dict[str, str] = {}
    if not isinstance(headers, dict):
        return result
    for name, value in headers.items():
        if isinstance(name, str) and isinstance(value, str):
            result[name.lower()] = value
    return result


def _as_bytes(body: object) -> bytes:
    """Return the body as bytes; text is UTF-8 encoded, other types give b""."""
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    if isinstance(body, str):
        try:
            return body.encode("utf-8")
        except UnicodeError:
            return b""
    return b""


def _lagos_now() -> datetime:
    """Return the current time at the Lagos offset (+01:00)."""
    return datetime.now(LAGOS)


def _same(first: str, second: str) -> bool:
    """Compare two texts in constant time."""
    return hmac.compare_digest(first.encode("utf-8"), second.encode("utf-8"))


# --- GET verification and signature ---------------------------------------


def verify_subscription(query: object, verify_token: object) -> str | None:
    """Return the challenge when mode, token and challenge are right, else None.

    Why: Meta registers the webhook with this handshake. An unset token never
    matches, so a missing setting cannot open the endpoint.
    """
    if not isinstance(query, dict):
        return None
    if not isinstance(verify_token, str) or not verify_token:
        return None
    mode = query.get("hub.mode")
    supplied = query.get("hub.verify_token")
    challenge = query.get("hub.challenge")
    if mode != "subscribe":
        return None
    if not isinstance(supplied, str) or not isinstance(challenge, str):
        return None
    if not challenge or not _same(supplied, verify_token):
        return None
    return challenge


def verify_signature(raw_body: bytes, header: object, app_secret: object) -> bool:
    """True only for a non-empty secret and a matching ``sha256=`` header.

    Why: only Meta knows the app secret, so only Meta can sign the raw bytes.
    """
    if not isinstance(raw_body, bytes):
        return False
    if not isinstance(header, str) or not isinstance(app_secret, str) or not app_secret:
        return False
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return _same("sha256=" + digest, header)


# --- Payload parsing --------------------------------------------------------


def _items(value: object) -> list[dict]:
    """Return the dict items of a list; anything else counts as empty."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _clean_id(value: object) -> str | None:
    """Return a usable message id, or None."""
    if isinstance(value, str) and 0 < len(value) <= _MAX_ID_CHARS:
        return value
    return None


def _to_message(raw: dict) -> IncomingMessage | None:
    """Turn one raw message into an IncomingMessage, or None to skip it."""
    kind = raw.get("type")
    sender = raw.get("from")
    if not isinstance(kind, str) or not kind:
        return None
    if not isinstance(sender, str) or not _SENDER_RE.fullmatch(sender):
        return None
    message_id = _clean_id(raw.get("id"))
    if kind != "text":
        return IncomingMessage(message_id, sender, "other", None)
    text = raw.get("text")
    body = text.get("body") if isinstance(text, dict) else None
    if not isinstance(body, str):
        return None
    return IncomingMessage(message_id, sender, "text", body)


def extract_messages(payload: object) -> list[IncomingMessage]:
    """Read entry[].changes[].value.messages[] defensively, in order.

    Why: the payload is untrusted shape. A missing or wrongly typed level counts
    as empty and a malformed message is skipped.
    """
    found: list[IncomingMessage] = []
    if not isinstance(payload, dict):
        return found
    for entry in _items(payload.get("entry")):
        for change in _items(entry.get("changes")):
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            for raw in _items(value.get("messages")):
                message = _to_message(raw)
                if message is not None:
                    found.append(message)
    return found


# --- Outbound reply ---------------------------------------------------------


def build_reply_request(
    phone_number_id: str, access_token: str, sender: str, reply: str
) -> tuple[str, dict[str, str], bytes]:
    """Build the URL, headers and JSON body for one outbound WhatsApp message."""
    url = GRAPH_URL_TEMPLATE.format(
        version=GRAPH_API_VERSION, phone_number_id=phone_number_id
    )
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "text",
        "text": {"body": reply},
    }
    return url, headers, json.dumps(payload).encode("utf-8")


def default_send(
    url: str, headers: dict, body: bytes, timeout: float
) -> tuple[int, bytes]:
    """POST once with urllib. An HTTP error status is returned, not raised."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status), response.read(_MAX_RESPONSE_READ)
    except urllib.error.HTTPError as exc:
        return int(exc.code), b""


def _send_reply(sender: str, reply: str, send: SendFunction) -> None:
    """Send one reply if the settings allow it. Failures are logged, not raised."""
    token = _env("WHATSAPP_TOKEN")
    phone_id = _env("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not _PHONE_ID_RE.fullmatch(phone_id):
        _log_event("send_skipped")
        return
    try:
        url, headers, body = build_reply_request(phone_id, token, sender, reply)
        status, _ = send(url, headers, body, SEND_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - a failed send must not stop the webhook
        _log_event("webhook_send_failed", type(exc).__name__)
        return
    if not isinstance(status, int) or not 200 <= status <= 299:
        _log_event("webhook_send_failed", status if isinstance(status, int) else None)


# --- Message processing -----------------------------------------------------


def _resolve_explainer(explainer: object) -> object:
    """Return the injected explainer, else get_explainer(), else the template one."""
    if explainer is not None:
        return explainer
    try:
        from ghost_credit.ai_explainer import get_explainer

        return get_explainer()
    except Exception:  # noqa: BLE001 - a missing or broken module means the free default
        return TemplateExplainer()


def _reply_for_text(text: str, deps: dict) -> str:
    """Run the check on the text and return the reply it wrote."""
    category = _env("MERCHANT_CATEGORY") or "other"
    clock = deps["clock"] or _lagos_now
    check = deps["check"] or run_check
    result = check(
        text[:MAX_TEXT_CHARS],
        None,
        None,
        category,
        clock(),
        reader=FakeScreenshotReader() if deps["reader"] is None else deps["reader"],
        paystack_verify=(
            make_paystack_verify()
            if deps["paystack_verify"] is None
            else deps["paystack_verify"]
        ),
        network=get_network() if deps["network"] is None else deps["network"],
        explainer=_resolve_explainer(deps["explainer"]),
    )
    reply = result.reply
    if not isinstance(reply, str):
        raise TypeError("reply is not text")
    return reply[:MAX_REPLY_CHARS]


def _process_message(message: IncomingMessage, deps: dict) -> None:
    """Check or answer one message. Any failure is logged and dropped."""
    try:
        if message.kind == "text":
            reply = _reply_for_text(message.text or "", deps)
        else:
            reply = ASK_FOR_SMS_REPLY
        _send_reply(message.sender, reply, deps["send"] or default_send)
    except Exception as exc:  # noqa: BLE001 - one bad message must not stop the rest
        _log_event("webhook_message_failed", type(exc).__name__)


def _handle_post_body(raw: bytes, deps: dict) -> None:
    """Parse a signed body and process each message in order."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        _log_event("webhook_bad_json")
        return
    seen = _DEFAULT_SEEN if deps["seen"] is None else deps["seen"]
    for message in extract_messages(payload):
        if message.message_id is not None and not seen.add_if_new(message.message_id):
            _log_event("webhook_duplicate")
            continue
        _process_message(message, deps)


def _forbidden() -> WebhookResponse:
    """Return the fixed 403 answer."""
    return WebhookResponse(403, BODY_FORBIDDEN)


def handle_webhook(
    method: object,
    query: object,
    headers: object,
    body: object,
    *,
    send: SendFunction | None = None,
    clock: Callable[[], datetime] | None = None,
    check: Callable | None = None,
    reader: object = None,
    paystack_verify: Callable | None = None,
    network: object = None,
    explainer: object = None,
    seen: SeenSet | None = None,
) -> WebhookResponse:
    """Answer one webhook call. It never raises.

    GET answers Meta's verification. POST checks size, then the signature,
    then runs each text message through the pipeline and replies. Before the
    signature passes any failure is 403; after it, any failure is 200.
    """
    deps = {
        "send": send, "clock": clock, "check": check, "reader": reader,
        "paystack_verify": paystack_verify, "network": network,
        "explainer": explainer, "seen": seen,
    }
    authenticated = False
    try:
        verb = method.upper() if isinstance(method, str) else ""
        if verb == "GET":
            challenge = verify_subscription(query, _env("WHATSAPP_VERIFY_TOKEN"))
            if challenge is None:
                return _forbidden()
            return WebhookResponse(200, challenge)
        if verb != "POST":
            return WebhookResponse(405, BODY_NOT_ALLOWED)
        raw = _as_bytes(body)
        if len(raw) > MAX_BODY_BYTES:
            _log_event("webhook_too_large")
            return WebhookResponse(413, BODY_TOO_LARGE)
        header = _normalise_headers(headers).get("x-hub-signature-256")
        if not verify_signature(raw, header, _env("WHATSAPP_APP_SECRET")):
            _log_event("webhook_forbidden")
            return _forbidden()
        authenticated = True
        _handle_post_body(raw, deps)
        return WebhookResponse(200, BODY_OK)
    except Exception as exc:  # noqa: BLE001 - the handler must never raise
        _log_event("webhook_unexpected_error", type(exc).__name__)
        return WebhookResponse(200, BODY_OK) if authenticated else _forbidden()
