"""Example tests for the webhook request gate."""

from __future__ import annotations

from ghost_credit import whatsapp
from ghost_credit.whatsapp import MAX_BODY_BYTES, SeenSet, handle_webhook
from whatsapp_fakes import (
    APP_SECRET, VERIFY_TOKEN, FakeCheck, RecordingSend, fake_env, sign,
    signed_headers, text_message, to_bytes, wrap_messages,
)


def _post(body: bytes, headers: dict | None = None, **deps):
    deps.setdefault("send", RecordingSend())
    deps.setdefault("check", FakeCheck())
    deps.setdefault("seen", SeenSet())
    with fake_env():
        return handle_webhook(
            "POST", {}, signed_headers(body) if headers is None else headers, body, **deps
        )


def test_body_over_the_limit_is_413_and_not_processed() -> None:
    check, send = FakeCheck(), RecordingSend()
    response = _post(b"x" * (MAX_BODY_BYTES + 1), check=check, send=send)
    assert response.status == 413
    assert check.calls == [] and send.calls == []


def test_body_at_the_limit_is_accepted() -> None:
    body = b"x" * MAX_BODY_BYTES
    assert _post(body).status == 200


def test_put_is_405() -> None:
    with fake_env():
        assert handle_webhook("PUT", {}, {}, b"").status == 405


def test_bad_signature_example() -> None:
    body = to_bytes(wrap_messages([text_message("hello")]))
    check = FakeCheck()
    response = _post(body, {"X-Hub-Signature-256": sign(body, "other-secret")}, check=check)
    assert response.status == 403 and check.calls == []


def test_signature_over_non_utf8_bytes_is_accepted() -> None:
    body = b"\xff\xfe\x00\x80 not json"
    send = RecordingSend()
    assert _post(body, send=send).status == 200
    assert send.calls == []


def test_token_is_read_at_request_time() -> None:
    query = {"hub.mode": "subscribe", "hub.verify_token": "tok-a", "hub.challenge": "42"}
    with fake_env(WHATSAPP_VERIFY_TOKEN="tok-a"):
        assert handle_webhook("GET", query, {}, b"").status == 200
    with fake_env(WHATSAPP_VERIFY_TOKEN="tok-b"):
        assert handle_webhook("GET", query, {}, b"").status == 403
    assert VERIFY_TOKEN != "tok-a"


def test_secret_is_read_at_request_time() -> None:
    body = b"{}"
    headers = {"x-hub-signature-256": sign(body, "secret-one")}
    with fake_env(WHATSAPP_APP_SECRET="secret-one"):
        assert handle_webhook("POST", {}, headers, body).status == 200
    with fake_env(WHATSAPP_APP_SECRET="secret-two"):
        assert handle_webhook("POST", {}, headers, body).status == 403


def test_header_names_are_case_insensitive() -> None:
    body = b"{}"
    with fake_env():
        headers = {"X-HUB-signature-256": sign(body, APP_SECRET)}
        assert handle_webhook("POST", {}, headers, body).status == 200


def test_unexpected_error_before_signature_passes_is_403(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(whatsapp, "verify_signature", boom)
    check = FakeCheck()
    body = b"{}"
    response = _post(body, check=check)
    assert (response.status, response.body) == (403, "forbidden")
    assert check.calls == []


def test_unexpected_error_after_signature_passes_is_200(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(whatsapp, "extract_messages", boom)
    body = to_bytes(wrap_messages([text_message("hello")]))
    assert _post(body).status == 200
