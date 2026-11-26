"""Feature: whatsapp-webhook, Property 7: A repeated message is processed once."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.whatsapp import SeenSet
from whatsapp_fakes import (
    FakeCheck, RecordingSend, fake_env, post, text_message, to_bytes, wrap_messages,
)

ids = st.lists(st.integers(min_value=0, max_value=6).map(lambda n: f"wamid.{n}"),
               min_size=1, max_size=8)


def _deliver(body: bytes, seen: SeenSet):
    check, send = FakeCheck(), RecordingSend()
    with fake_env():
        post(body, check=check, send=send, seen=seen)
    return check, send


@settings(max_examples=100, deadline=None)
@given(ids)
def test_second_delivery_changes_nothing(message_ids) -> None:
    """**Validates: Requirements 7.3, 7.4**"""
    messages = [text_message(f"alert {i}", message_id=m) for i, m in enumerate(message_ids)]
    body = to_bytes(wrap_messages(messages))
    once_check, once_send = _deliver(body, SeenSet())

    seen = SeenSet()
    first_check, first_send = _deliver(body, seen)
    second_check, second_send = _deliver(body, seen)

    assert len(second_check.calls) == 0 and len(second_send.calls) == 0
    assert len(first_check.calls) == len(once_check.calls) == len(set(message_ids))
    assert len(first_send.calls) == len(once_send.calls)
