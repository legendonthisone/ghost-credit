"""Feature: whatsapp-webhook, Property 11: Lambda body decoding keeps the raw bytes."""

from __future__ import annotations

import base64

from hypothesis import given, settings, strategies as st

from ghost_credit import lambda_handler as lh
from ghost_credit.whatsapp import WebhookResponse


def _capture(monkeypatch_target, event) -> list:
    """Run the adapter with a recording handle_webhook and return the bodies."""
    seen: list = []

    def fake(method, query, headers, body, **deps):
        seen.append(body)
        return WebhookResponse(200, "ok")

    original = lh.handle_webhook
    lh.handle_webhook = fake
    try:
        lh.lambda_handler(event, None)
    finally:
        lh.handle_webhook = original
    return seen


@settings(max_examples=150, deadline=None)
@given(st.binary(max_size=500))
def test_base64_body_decodes_to_the_same_bytes(raw) -> None:
    """**Validates: Requirements 11.2**"""
    event = {
        "requestContext": {"http": {"method": "POST"}},
        "body": base64.b64encode(raw).decode("ascii"),
        "isBase64Encoded": True,
    }
    assert _capture(None, event) == [raw]


@settings(max_examples=150, deadline=None)
@given(st.text(max_size=300), st.sampled_from([False, None, "missing"]))
def test_text_body_encodes_as_utf8(text, flag) -> None:
    """**Validates: Requirements 11.3**"""
    try:
        expected = text.encode("utf-8")
    except UnicodeError:
        return
    event = {"requestContext": {"http": {"method": "POST"}}, "body": text}
    if flag != "missing":
        event["isBase64Encoded"] = flag
    assert _capture(None, event) == [expected]
