"""Feature: whatsapp-webhook, Property 4: Long text is cut to 2000 characters."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from whatsapp_fakes import FakeCheck, RecordingSend, fake_env, post, text_message, to_bytes, wrap_messages

# Mix short texts with texts around and far above the 2000 character limit.
texts = st.one_of(
    st.text(max_size=100),
    st.integers(min_value=1995, max_value=2005).map(lambda n: "a" * n),
    st.text(min_size=2000, max_size=4500),
)


@settings(max_examples=100, deadline=None)
@given(texts)
def test_text_is_cut_to_2000_characters(text) -> None:
    """**Validates: Requirements 4.2**"""
    body = to_bytes(wrap_messages([text_message(text)]))
    check = FakeCheck()
    with fake_env():
        response = post(body, check=check, send=RecordingSend())
    assert response.status == 200
    assert len(check.calls) == 1
    assert check.calls[0][0] == text[: min(len(text), 2000)]
