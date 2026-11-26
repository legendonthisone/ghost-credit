"""Feature: whatsapp-webhook, Property 5: A signed non-text message gets the fixed ask and no check."""

from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from ghost_credit.whatsapp import ASK_FOR_SMS_REPLY
from whatsapp_fakes import (
    FakeCheck, RecordingSend, fake_env, post, senders, to_bytes, wrap_messages,
)

kinds = st.one_of(
    st.sampled_from(["image", "audio", "document", "sticker", "video", "location",
                     "reaction", "button", "unsupported"]),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=12).filter(
        lambda s: s != "text"
    ),
)
media = st.one_of(st.none(), st.just({"id": "media-1", "mime_type": "image/jpeg"}), st.just("junk"))


@settings(max_examples=120, deadline=None)
@given(senders, kinds, media)
def test_non_text_gets_the_fixed_ask(sender, kind, media_part) -> None:
    """**Validates: Requirements 5.1, 5.2, 5.3**"""
    message = {"from": sender, "id": "wamid.NT1", "type": kind}
    if media_part is not None:
        message[kind] = media_part
    body = to_bytes(wrap_messages([message]))
    check, send = FakeCheck(), RecordingSend()
    with fake_env():
        response = post(body, check=check, send=send)
    assert response.status == 200
    assert check.calls == []
    assert len(send.calls) == 1
    url, _, raw, _ = send.calls[0]
    assert url.endswith("/messages")  # the only request is the reply itself
    payload = json.loads(raw)
    assert payload["to"] == sender
    assert payload["text"]["body"] == ASK_FOR_SMS_REPLY
