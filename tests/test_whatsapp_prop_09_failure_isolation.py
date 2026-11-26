"""Feature: whatsapp-webhook, Property 9: One failing message does not stop the rest."""

from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from whatsapp_fakes import (
    FakeCheck, RecordingSend, fake_env, post, text_message, to_bytes, wrap_messages,
)


@settings(max_examples=100, deadline=None)
@given(st.lists(st.booleans(), min_size=1, max_size=8), st.booleans())
def test_failures_are_skipped_and_order_is_kept(fails, send_fails_on_first) -> None:
    """**Validates: Requirements 3.5, 7.1, 7.2, 9.2**"""
    count = len(fails)
    senders = [f"23480000{n:05d}" for n in range(count)]
    texts = [f"alert number {n}" for n in range(count)]
    messages = [text_message(texts[n], senders[n], f"wamid.{n}") for n in range(count)]
    check = FakeCheck(raise_for={texts[n] for n in range(count) if fails[n]})
    send = RecordingSend()
    if send_fails_on_first:
        # The first send raises; the later messages must still be answered.
        original = send.__call__
        state = {"first": True}

        def flaky(url, headers, body, timeout):
            result = original(url, headers, body, timeout)
            if state["first"]:
                state["first"] = False
                raise OSError("fake send failure")
            return result

        send_fn = flaky
    else:
        send_fn = send
    with fake_env():
        response = post(to_bytes(wrap_messages(messages)), check=check, send=send_fn)
    assert response.status == 200
    expected = [senders[n] for n in range(count) if not fails[n]]
    assert [json.loads(call[2])["to"] for call in send.calls] == expected
    assert [call[0] for call in check.calls] == texts
