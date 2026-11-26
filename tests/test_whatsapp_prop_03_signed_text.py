"""Feature: whatsapp-webhook, Property 3: A signed text message gets one check and one reply."""

from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from ghost_credit.whatsapp import MAX_REPLY_CHARS
from whatsapp_fakes import (
    ACCESS_TOKEN, FIXED_NOW, PHONE_ID, FakeCheck, RecordingSend, fake_env,
    message_ids, post, reply_texts, senders, text_message, to_bytes, wrap_messages,
)


@settings(max_examples=120, deadline=None)
@given(senders, message_ids, st.text(min_size=1, max_size=200), reply_texts)
def test_signed_text_gets_one_check_and_one_reply(sender, message_id, text, reply) -> None:
    """**Validates: Requirements 4.1, 4.3, 4.9, 4.10, 6.1, 6.2, 6.3, 6.4, 7.1**"""
    body = to_bytes(wrap_messages([text_message(text, sender, message_id)]))
    check, send = FakeCheck(reply=reply), RecordingSend()
    with fake_env():
        response = post(body, check=check, send=send)
    assert response.status == 200
    assert check.calls == [(text, None, None, "other", FIXED_NOW)]
    assert len(send.calls) == 1
    url, headers, raw, timeout = send.calls[0]
    assert url == f"https://graph.facebook.com/v21.0/{PHONE_ID}/messages"
    assert headers == {
        "Authorization": "Bearer " + ACCESS_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "ghost-credit/0.1",
    }
    assert timeout == 5.0
    assert json.loads(raw) == {
        "messaging_product": "whatsapp",
        "to": sender,
        "type": "text",
        "text": {"body": reply[:MAX_REPLY_CHARS]},
    }
