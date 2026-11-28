"""Example tests for recorded payloads, wiring and the outbound call."""

from __future__ import annotations

import io
import json
import logging
import sys
import types
import urllib.error

from ghost_credit import whatsapp
from ghost_credit.pattern_network import NoopPatternNetwork
from ghost_credit.screenshot import FakeScreenshotReader
from ghost_credit.verdict import TemplateExplainer
from ghost_credit.whatsapp import (
    ASK_FOR_SMS_REPLY, SeenSet, build_reply_request, default_send, extract_messages,
    handle_webhook,
)
from whatsapp_fakes import (
    ACCESS_TOKEN, FIXED_NOW, PHONE_ID, SENDER, FakeCheck, FakeExplainer, RecordingGet, RecordingSend,
    fake_env, image_message, post, sign, status_payload, text_message, to_bytes,
    wrap_messages,
)

SMS = "Credit Alert: NGN 45,000.00 CR Acct 012****789 Bal NGN 90,000.00"


def _go(payload: object, **deps):
    deps.setdefault("check", FakeCheck())
    deps.setdefault("send", RecordingSend())
    with fake_env():
        response = post(to_bytes(payload), **deps)
    return response, deps["check"], deps["send"]


# --- Recorded payloads --------------------------------------------------------


def test_recorded_text_payload() -> None:
    response, check, send = _go(wrap_messages([text_message(SMS)]))
    assert response.status == 200 and response.body == "ok"
    assert [c[0] for c in check.calls] == [SMS]
    assert len(send.calls) == 1


def test_recorded_image_payload_with_failed_download_gets_the_ask() -> None:
    get = RecordingGet(raises=RuntimeError("down"))
    response, check, send = _go(wrap_messages([image_message()]), get=get)
    assert response.status == 200
    assert check.calls == []
    assert len(send.calls) == 1
    assert send.sent_bodies()[0]["text"]["body"] == ASK_FOR_SMS_REPLY


def test_status_update_payload_does_nothing() -> None:
    response, check, send = _go(status_payload())
    assert response.status == 200
    assert check.calls == [] and send.calls == []


def test_duplicate_message_id_is_processed_once() -> None:
    seen = SeenSet()
    payload = wrap_messages([text_message(SMS, message_id="wamid.DUP")])
    _, check, send = _go(payload, seen=seen)
    _, check2, send2 = _go(payload, seen=seen)
    assert len(check.calls) == 1 and len(send.calls) == 1
    assert check2.calls == [] and send2.calls == []


def test_over_long_text_is_cut() -> None:
    _, check, _ = _go(wrap_messages([text_message("x" * 5000)]))
    assert len(check.calls[0][0]) == 2000


def test_invalid_json_gives_200_and_sends_nothing() -> None:
    body = b"{not json"
    send, check = RecordingSend(), FakeCheck()
    with fake_env():
        response = post(body, send=send, check=check)
    assert response.status == 200
    assert send.calls == [] and check.calls == []


def test_bad_sender_and_missing_type_are_skipped() -> None:
    good = text_message(SMS, message_id="wamid.OK")
    bad_from = text_message(SMS, "+2348000000001", "wamid.B1")
    long_from = text_message(SMS, "1" * 21, "wamid.B2")
    no_type = {"from": SENDER, "id": "wamid.B3", "text": {"body": SMS}}
    no_body = {"from": SENDER, "id": "wamid.B4", "type": "text", "text": {}}
    _, check, send = _go(wrap_messages([bad_from, long_from, no_type, no_body, good]))
    assert len(check.calls) == 1 and len(send.calls) == 1


def test_two_messages_are_answered_in_order() -> None:
    messages = [text_message("first", "2348000000001", "wamid.1"),
                text_message("second", "2348000000002", "wamid.2")]
    _, check, send = _go(wrap_messages(messages))
    assert [c[0] for c in check.calls] == ["first", "second"]
    assert [b["to"] for b in send.sent_bodies()] == ["2348000000001", "2348000000002"]


def test_wrongly_typed_levels_count_as_empty() -> None:
    for payload in ({"entry": 5}, {"entry": [None, {"changes": "x"}]},
                    {"entry": [{"changes": [{"value": {"messages": "x"}}]}]}, [], "text", 7):
        assert extract_messages(payload) == []


def test_message_without_id_is_still_processed() -> None:
    message = text_message(SMS)
    del message["id"]
    _, check, _ = _go(wrap_messages([message]))
    assert len(check.calls) == 1


# --- Default wiring -----------------------------------------------------------


def test_defaults_are_the_real_parts() -> None:
    check = FakeCheck()
    _go(wrap_messages([text_message(SMS)]), check=check)
    kwargs = check.kwargs[0]
    assert isinstance(kwargs["reader"], FakeScreenshotReader)
    assert isinstance(kwargs["network"], NoopPatternNetwork)
    assert callable(kwargs["paystack_verify"])
    assert isinstance(kwargs["explainer"], TemplateExplainer)


def test_injected_parts_are_passed_through() -> None:
    check, explainer = FakeCheck(), FakeExplainer()
    reader, network = FakeScreenshotReader(), NoopPatternNetwork()
    paystack = lambda parsed, now: None  # noqa: E731
    _go(wrap_messages([text_message(SMS)]), check=check, explainer=explainer,
        reader=reader, network=network, paystack_verify=paystack)
    kwargs = check.kwargs[0]
    assert kwargs["explainer"] is explainer and kwargs["reader"] is reader
    assert kwargs["network"] is network and kwargs["paystack_verify"] is paystack


def test_real_pipeline_runs_offline_with_no_paystack_key(monkeypatch) -> None:
    monkeypatch.delenv("PAYSTACK_SECRET_KEY", raising=False)
    send = RecordingSend()
    with fake_env():
        response = post(to_bytes(wrap_messages([text_message(SMS)])), send=send)
    assert response.status == 200
    reply = send.sent_bodies()[0]["text"]["body"]
    assert "Check your own bank app before releasing goods." in reply


def test_merchant_category_comes_from_the_environment() -> None:
    check = FakeCheck()
    body = to_bytes(wrap_messages([text_message(SMS)]))
    with fake_env(MERCHANT_CATEGORY="salon"):
        post(body, check=check, send=RecordingSend())
    with fake_env(MERCHANT_CATEGORY="   "):
        post(body, check=check, send=RecordingSend(), seen=SeenSet())
    assert [c[3] for c in check.calls] == ["salon", "other"]
    assert check.calls[0][4] == FIXED_NOW


def test_default_clock_is_lagos_time() -> None:
    now = whatsapp._lagos_now()
    assert now.utcoffset().total_seconds() == 3600


# --- Explainer choice ---------------------------------------------------------


def _explainer_used(monkeypatch, module) -> object:
    monkeypatch.setitem(sys.modules, "ghost_credit.ai_explainer", module)
    check = FakeCheck()
    _go(wrap_messages([text_message(SMS)]), check=check)
    return check.kwargs[0]["explainer"]


def test_get_explainer_is_used_with_no_arguments(monkeypatch) -> None:
    sentinel, calls = object(), []
    module = types.ModuleType("ghost_credit.ai_explainer")
    module.get_explainer = lambda *a, **k: (calls.append((a, k)), sentinel)[1]
    assert _explainer_used(monkeypatch, module) is sentinel
    assert calls == [((), {})]


def test_missing_explainer_module_falls_back_to_template(monkeypatch) -> None:
    assert isinstance(_explainer_used(monkeypatch, None), TemplateExplainer)


def test_raising_get_explainer_falls_back_to_template(monkeypatch) -> None:
    module = types.ModuleType("ghost_credit.ai_explainer")

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    module.get_explainer = boom
    assert isinstance(_explainer_used(monkeypatch, module), TemplateExplainer)


def test_real_explainer_module_defaults_to_template(monkeypatch) -> None:
    monkeypatch.delenv("EXPLAINER", raising=False)
    check = FakeCheck()
    _go(wrap_messages([text_message(SMS)]), check=check)
    assert isinstance(check.kwargs[0]["explainer"], TemplateExplainer)


# --- Sending ------------------------------------------------------------------


def test_send_uses_five_seconds_and_one_attempt() -> None:
    _, _, send = _go(wrap_messages([text_message(SMS)]))
    assert len(send.calls) == 1 and send.calls[0][3] == 5.0


def test_raising_send_is_logged_by_type_name(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    send = RecordingSend(raises=OSError("secret detail"))
    response, _, _ = _go(wrap_messages([text_message(SMS)]), send=send)
    assert response.status == 200
    assert "webhook_send_failed OSError" in caplog.text
    assert "secret detail" not in caplog.text


def test_non_2xx_status_is_logged(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    response, _, send = _go(wrap_messages([text_message(SMS)]), send=RecordingSend(status=401))
    assert response.status == 200 and len(send.calls) == 1
    assert "webhook_send_failed 401" in caplog.text


def _skipped(caplog, **env) -> RecordingSend:
    caplog.set_level(logging.DEBUG)
    send, body = RecordingSend(), to_bytes(wrap_messages([text_message(SMS)]))
    with fake_env(**env):
        response = post(body, send=send, check=FakeCheck())
    assert response.status == 200
    assert "send_skipped" in caplog.text
    return send


def test_send_skipped_without_token(caplog) -> None:
    assert _skipped(caplog, WHATSAPP_TOKEN=None).calls == []


def test_send_skipped_with_empty_token(caplog) -> None:
    assert _skipped(caplog, WHATSAPP_TOKEN="").calls == []


def test_send_skipped_without_phone_number_id(caplog) -> None:
    assert _skipped(caplog, WHATSAPP_PHONE_NUMBER_ID=None).calls == []


def test_send_skipped_for_malformed_phone_number_id(caplog) -> None:
    assert _skipped(caplog, WHATSAPP_PHONE_NUMBER_ID="12ab").calls == []


def test_send_skipped_for_33_digit_phone_number_id(caplog) -> None:
    assert _skipped(caplog, WHATSAPP_PHONE_NUMBER_ID="1" * 33).calls == []


def test_build_reply_request_shape() -> None:
    url, headers, raw = build_reply_request(PHONE_ID, ACCESS_TOKEN, SENDER, "hi")
    assert url == f"https://graph.facebook.com/{whatsapp.GRAPH_API_VERSION}/{PHONE_ID}/messages"
    assert headers["Authorization"] == "Bearer " + ACCESS_TOKEN
    assert json.loads(raw)["to"] == SENDER


def test_default_send_posts_once_with_timeout(monkeypatch) -> None:
    seen = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            return b"{}"

    def fake_urlopen(request, timeout=None):
        seen["method"], seen["url"] = request.get_method(), request.full_url
        seen["timeout"], seen["data"] = timeout, request.data
        return Response()

    monkeypatch.setattr(whatsapp.urllib.request, "urlopen", fake_urlopen)
    status, _ = default_send("https://graph.facebook.com/x", {"A": "b"}, b"{}", 5.0)
    assert status == 200
    assert seen == {"method": "POST", "url": "https://graph.facebook.com/x",
                    "timeout": 5.0, "data": b"{}"}


def test_default_send_returns_http_error_status(monkeypatch) -> None:
    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 400, "bad", {}, io.BytesIO(b""))

    monkeypatch.setattr(whatsapp.urllib.request, "urlopen", fake_urlopen)
    assert default_send("https://graph.facebook.com/x", {}, b"{}", 5.0)[0] == 400


def test_handle_webhook_signature_header_example() -> None:
    body = to_bytes(wrap_messages([text_message(SMS)]))
    with fake_env():
        response = handle_webhook(
            "POST", {}, {"x-hub-signature-256": sign(body)}, body,
            send=RecordingSend(), check=FakeCheck(), seen=SeenSet(),
        )
    assert response.status == 200
