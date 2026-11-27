"""Example tests for how The Lab is wired into the Lambda and the webhook."""

from __future__ import annotations

import json

from ghost_credit import lambda_handler as lh
from ghost_credit import lab_router
from ghost_credit.whatsapp import WebhookResponse
from lab_fakes import FakeRunCheck, RaisingStore, SpyStore, make_result
from whatsapp_fakes import (
    RecordingSend, post, set_env, text_message, to_bytes, wrap_messages,
)


def test_non_lab_event_reaches_handle_webhook(monkeypatch) -> None:
    """A path outside /lab still goes to handle_webhook, not the router."""
    calls: list[tuple] = []
    monkeypatch.setattr(
        lh, "handle_webhook",
        lambda *a, **k: calls.append(a) or WebhookResponse(200, "ok"),
    )
    monkeypatch.setattr(lab_router, "route", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    event = {"rawPath": "/webhook", "requestContext": {"http": {"method": "POST"}}, "body": "x"}
    out = lh.lambda_handler(event, None)
    assert len(calls) == 1 and out["statusCode"] == 200 and out["body"] == "ok"


def test_lab_event_is_routed_to_lab_router(monkeypatch) -> None:
    """A /lab event goes to lab_router.route and its answer is returned."""
    seen: list[tuple] = []

    def fake_route(method, path, query, headers, raw, **kw):
        seen.append((method, path, kw["limiter"] is lh._LIMITER))
        return 200, {"Content-Type": "text/plain"}, "lab body"

    monkeypatch.setattr(lab_router, "route", fake_route)
    monkeypatch.setattr(lh, "handle_webhook", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    event = {"rawPath": "/lab/data", "requestContext": {"http": {"method": "GET"}}}
    out = lh.lambda_handler(event, None)
    assert seen == [("GET", "/lab/data", True)]
    assert out == {"statusCode": 200, "headers": {"Content-Type": "text/plain"}, "body": "lab body"}


def test_real_lab_page_through_lambda(monkeypatch) -> None:
    """GET /lab through the Lambda adapter returns the page with the headers."""
    monkeypatch.delenv("CHECKS_TABLE", raising=False)
    event = {"rawPath": "/lab", "requestContext": {"http": {"method": "GET"}}}
    out = lh.lambda_handler(event, None)
    assert out["statusCode"] == 200
    assert out["headers"]["Cache-Control"] == "no-store"
    assert json.loads(lh.lambda_handler(
        {"rawPath": "/lab/data", "requestContext": {"http": {"method": "GET"}}}, None
    )["body"])["records"] == []


def test_whatsapp_text_check_records_once_with_channel(monkeypatch) -> None:
    """One WhatsApp text check saves exactly one record, channel whatsapp."""
    set_env(monkeypatch)
    store = SpyStore()
    body = to_bytes(wrap_messages([text_message("hi", message_id="wamid.W1")]))
    post(body, send=RecordingSend(), check=FakeRunCheck(), store=store)
    assert len(store.saved) == 1 and store.saved[0]["channel"] == "whatsapp"


def test_whatsapp_reply_is_sent_even_if_store_fails(monkeypatch) -> None:
    """A store that raises never stops or changes the reply."""
    set_env(monkeypatch)
    send = RecordingSend()
    reply = make_result().reply
    body = to_bytes(wrap_messages([text_message("hi", message_id="wamid.W2")]))
    out = post(body, send=send, check=FakeRunCheck(), store=RaisingStore(RuntimeError("x")))
    assert out.status == 200 and len(send.calls) == 1
    assert send.sent_bodies()[0]["text"]["body"] == reply
