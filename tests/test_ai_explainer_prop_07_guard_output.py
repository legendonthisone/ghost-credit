"""Feature: ai-explainer, Property 7: Accepted model text is clean and short."""

from __future__ import annotations

import re

from hypothesis import given, settings, strategies as st

from ai_explainer_helpers import CODES
from ghost_credit.ai_explainer import guard_output

_texts = st.one_of(
    st.text(max_size=1500),
    st.lists(st.sampled_from(["Hello there. ", "Take care! ", "a\x00b\r\n\n\n\n", "12345678 ", "word "]),
             max_size=300).map("".join),
    st.none(),
    st.integers(),
)


# **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.8**
@settings(max_examples=200, deadline=None)
@given(text=_texts, code=st.one_of(st.sampled_from(CODES), st.text(max_size=5)))
def test_guard_output_is_clean_and_short(text: object, code: str) -> None:
    out = guard_output(text, code)
    if out is None:
        return
    assert isinstance(out, str)
    assert out.strip() != ""
    assert len(out) <= 600
    assert not any((c < " " and c != "\n") or c == "\x7f" for c in out)
    assert not re.search(r"\d{7,}", out)
    assert "\n\n\n" not in out
