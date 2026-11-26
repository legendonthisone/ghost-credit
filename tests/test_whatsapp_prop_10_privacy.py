"""Feature: whatsapp-webhook, Property 10: Logs, responses and replies hold no secret or customer data."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

from hypothesis import given, settings, strategies as st

from ghost_credit.whatsapp import SeenSet, handle_webhook
from whatsapp_fakes import (
    FIXED_NOW, REPLY, RecordingSend, fake_env, fake_secrets, sign, text_message,
    to_bytes, wrap_messages,
)


class _Capture(logging.Handler):
    """Collect every formatted log line."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


distinct_text = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 ", min_size=8, max_size=40
                        ).map(lambda s: "msg-" + s)
long_sender = st.text(alphabet="0123456789", min_size=10, max_size=15)
scenarios = st.sampled_from(["ok", "check_raises", "send_raises", "send_500", "bad_signature"])


@settings(max_examples=120, deadline=None)
@given(fake_secrets, fake_secrets, fake_secrets, distinct_text, long_sender, scenarios)
def test_nothing_sensitive_is_logged_or_returned(app, verify, token, text, sender, scenario) -> None:
    """**Validates: Requirements 8.1, 8.2, 8.3**"""
    if len({app, verify, token}) < 3:
        return
    body = to_bytes(wrap_messages([text_message(text, sender)]))
    signature = sign(body, app if scenario != "bad_signature" else app + "x")

    def check(t, s, i, c, n, **kwargs):
        if scenario == "check_raises":
            raise RuntimeError(t + sender + token)
        return SimpleNamespace(reply=REPLY)

    send = RecordingSend(
        status=500 if scenario == "send_500" else 200,
        raises=OSError(text + sender + token) if scenario == "send_raises" else None,
    )
    capture = _Capture()
    root = logging.getLogger()
    root.addHandler(capture)
    previous = root.level
    root.setLevel(logging.DEBUG)
    try:
        with fake_env(WHATSAPP_APP_SECRET=app, WHATSAPP_VERIFY_TOKEN=verify,
                      WHATSAPP_TOKEN=token):
            response = handle_webhook(
                "POST", {}, {"X-Hub-Signature-256": signature}, body,
                send=send, check=check, clock=lambda: FIXED_NOW, seen=SeenSet(),
            )
    finally:
        root.removeHandler(capture)
        root.setLevel(previous)

    secrets = [app, verify, token, signature]
    private = [text, sender]
    for line in capture.lines:
        for item in secrets + private:
            assert item not in line
    for item in secrets:
        assert item not in response.body
    for _, headers, raw, _ in send.calls:
        for item in secrets:
            assert item not in raw.decode("utf-8")
            for name, value in headers.items():
                if name != "Authorization":
                    assert item not in value
        assert headers["Authorization"] == "Bearer " + token
        assert json.loads(raw)["text"]["body"] == REPLY
