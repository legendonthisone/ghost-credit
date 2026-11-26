"""Feature: whatsapp-webhook, Property 6: GET verification matches the token."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.whatsapp import handle_webhook
from whatsapp_fakes import VERIFY_TOKEN, fake_env

env_tokens = st.sampled_from([None, "", VERIFY_TOKEN])
modes = st.sampled_from(["subscribe", "unsubscribe", "", None])
supplied = st.one_of(st.just(VERIFY_TOKEN), st.text(max_size=30), st.none())
challenges = st.one_of(st.text(min_size=1, max_size=20), st.just(""), st.none())


@settings(max_examples=200, deadline=None)
@given(env_tokens, modes, supplied, challenges)
def test_get_matches_exactly_when_token_matches(env_token, mode, token, challenge) -> None:
    """**Validates: Requirements 1.1, 1.3, 1.4**"""
    query = {}
    for key, value in (("hub.mode", mode), ("hub.verify_token", token),
                       ("hub.challenge", challenge)):
        if value is not None:
            query[key] = value
    with fake_env(WHATSAPP_VERIFY_TOKEN=env_token):
        response = handle_webhook("GET", query, {}, b"")
    should_pass = (
        mode == "subscribe" and bool(env_token) and token == env_token and bool(challenge)
    )
    if should_pass:
        assert (response.status, response.body) == (200, challenge)
    else:
        assert response.status == 403
        assert response.body == "forbidden"
