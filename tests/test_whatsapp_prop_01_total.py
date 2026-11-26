"""Feature: whatsapp-webhook, Property 1: The handler is total."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.whatsapp import SeenSet, WebhookResponse, handle_webhook
from whatsapp_fakes import (
    APP_SECRET, FakeCheck, RecordingSend, arbitrary_bodies, fake_env,
    header_values, methods, queries, sign,
)

secret_states = st.sampled_from([None, "", APP_SECRET, "  "])


@settings(max_examples=150, deadline=None)
@given(methods, queries, header_values, arbitrary_bodies, secret_states, st.booleans())
def test_handler_is_total(method, query, headers, body, secret, sign_it) -> None:
    """**Validates: Requirements 3.1, 9.1, 9.3**"""
    if sign_it and isinstance(body, bytes) and isinstance(headers, dict):
        headers = dict(headers)
        headers["x-hub-signature-256"] = sign(body)
    with fake_env(WHATSAPP_APP_SECRET=secret, WHATSAPP_VERIFY_TOKEN=secret):
        response = handle_webhook(
            method, query, headers, body,
            send=RecordingSend(), check=FakeCheck(), seen=SeenSet(),
        )
    assert isinstance(response, WebhookResponse)
    assert type(response.status) is int
    assert response.status in {200, 403, 405, 413}
