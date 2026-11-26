"""Feature: whatsapp-webhook, Property 2: Unproven requests are never processed."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.whatsapp import SeenSet, handle_webhook
from whatsapp_fakes import (
    APP_SECRET, FakeCheck, RecordingSend, fake_env, sign, text_message,
    to_bytes, wrap_messages,
)

# A body that would trigger a check if it were accepted.
VALID_BODY = to_bytes(wrap_messages([text_message("Credit alert NGN 5,000.00")]))

bodies = st.one_of(st.binary(max_size=500), st.just(VALID_BODY))
bad_headers = st.one_of(
    st.just({}),
    st.text(max_size=80).map(lambda s: {"X-Hub-Signature-256": s}),
    st.just({"X-Hub-Signature-256": "sha256="}),
    st.just({"X-Hub-Signature-256": "sha256=" + "0" * 64}),
    st.just({"X-Hub-Signature-256": 12345}),
)


def _run(body: bytes, headers: dict, secret: str | None):
    send, check = RecordingSend(), FakeCheck()
    with fake_env(WHATSAPP_APP_SECRET=secret):
        response = handle_webhook(
            "POST", {}, headers, body, send=send, check=check, seen=SeenSet()
        )
    return response, send, check


@settings(max_examples=120, deadline=None)
@given(bodies, bad_headers)
def test_bad_signature_is_refused(body, headers) -> None:
    """**Validates: Requirements 2.2, 2.3, 2.4, 2.7**"""
    response, send, check = _run(body, headers, APP_SECRET)
    assert response.status == 403
    assert check.calls == [] and send.calls == []


@settings(max_examples=120, deadline=None)
@given(bodies, st.text(min_size=1, max_size=20))
def test_signed_with_the_wrong_secret_is_refused(body, other) -> None:
    """**Validates: Requirements 2.3, 2.4**"""
    if other == APP_SECRET:
        other = other + "x"
    response, send, check = _run(body, {"X-Hub-Signature-256": sign(body, other)}, APP_SECRET)
    assert response.status == 403
    assert check.calls == [] and send.calls == []


@settings(max_examples=120, deadline=None)
@given(bodies, st.sampled_from([None, ""]), st.sampled_from([APP_SECRET, ""]))
def test_unset_secret_refuses_everything(body, secret, signed_with) -> None:
    """**Validates: Requirements 2.5**"""
    headers = {"X-Hub-Signature-256": sign(body, signed_with)}
    response, send, check = _run(body, headers, secret)
    assert response.status == 403
    assert check.calls == [] and send.calls == []
