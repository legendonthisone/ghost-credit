"""AWS Lambda adapter: hands Function URL calls to the WhatsApp webhook.

Function URL payload version 2.0 puts the method in ``requestContext.http``,
lowercases header names and base64-encodes some bodies. This module turns that
event into plain values for ``handle_webhook`` and turns the answer back into
the dict Lambda expects. It never raises. Secrets are read from the
environment inside ``whatsapp.py`` and nowhere else.
"""

from __future__ import annotations

import base64
import binascii

from datetime import datetime

from ghost_credit import lab_router
from ghost_credit.lab import SlidingWindowLimiter, get_store
from ghost_credit.pipeline import LAGOS
from ghost_credit.whatsapp import BODY_FORBIDDEN, SeenSet, handle_webhook

# One set per Lambda container, so repeated deliveries in it are skipped.
_SEEN = SeenSet()
# One rate-limit window per container for The Lab's "try an alert" form.
_LIMITER = SlidingWindowLimiter()


def _forbidden() -> dict:
    """Return the fixed 403 result."""
    return {
        "statusCode": 403,
        "headers": {"content-type": "text/plain"},
        "body": BODY_FORBIDDEN,
    }


def _raw_body(event: dict) -> bytes:
    """Return the raw body bytes: base64-decoded or UTF-8 encoded.

    Why: the signature is computed over the exact bytes Meta sent.
    """
    body = event.get("body")
    if body is None:
        return b""
    if not isinstance(body, str):
        raise ValueError("body is not text")
    if event.get("isBase64Encoded") is True:
        try:
            return base64.b64decode(body, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("bad base64") from exc
    return body.encode("utf-8")


def _method(event: dict) -> object:
    """Read requestContext.http.method, or None when missing."""
    context = event.get("requestContext")
    http = context.get("http") if isinstance(context, dict) else None
    return http.get("method") if isinstance(http, dict) else None


def _path(event: dict) -> str:
    """Read rawPath, or "/" when missing or not text."""
    path = event.get("rawPath")
    return path if isinstance(path, str) else "/"


def _lab_response(event: dict) -> dict:
    """Serve a /lab request through the Lab router."""
    status, headers, body = lab_router.route(
        _method(event) or "",
        _path(event),
        event.get("queryStringParameters"),
        _lower_headers(event.get("headers")),
        _raw_body(event),
        now=datetime.now(LAGOS),
        store=get_store(),
        limiter=_LIMITER,
    )
    return {"statusCode": int(status), "headers": headers, "body": body}


def _lower_headers(headers: object) -> dict:
    """Return headers with lowercase names; non-dict gives {}."""
    if not isinstance(headers, dict):
        return {}
    return {k.lower(): v for k, v in headers.items() if isinstance(k, str)}


def lambda_handler(event: object, context: object) -> dict:
    """Adapt a Function URL event to handle_webhook and back. Never raises."""
    try:
        if not isinstance(event, dict):
            return _forbidden()
        if _path(event).startswith("/lab"):
            return _lab_response(event)
        raw = _raw_body(event)
        response = handle_webhook(
            _method(event),
            event.get("queryStringParameters"),
            _lower_headers(event.get("headers")),
            raw,
            seen=_SEEN,
        )
        return {
            "statusCode": int(response.status),
            "headers": {"content-type": response.content_type},
            "body": str(response.body),
        }
    except Exception:  # noqa: BLE001 - signature not proven here, so fail closed
        return _forbidden()
