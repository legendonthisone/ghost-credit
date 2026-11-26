"""Feature: ai-explainer, Property 4: The reminder and the verdict survive the AI."""

from __future__ import annotations

import copy

from hypothesis import given, settings, strategies as st

from ai_explainer_helpers import (client_for, client_modes, codes, make_parsed, make_verdict,
                                  notes_list, reasons_list)
from ghost_credit.ai_explainer import BedrockExplainer
from ghost_credit.verdict import CHECK_REMINDER, build_reply


# **Validates: Requirements 4.4, 4.5**
@settings(max_examples=200, deadline=None)
@given(code=codes, reasons=reasons_list, notes=notes_list, mode=client_modes,
       text=st.one_of(st.text(max_size=200), st.just("Take care with this alert."),
                      st.just("Your payment is real.")),
       parsed_none=st.booleans())
def test_reminder_and_code_survive(code, reasons, notes, mode, text, parsed_none) -> None:
    verdict = make_verdict(code, reasons)
    parsed = None if parsed_none else make_parsed()
    snapshot = copy.deepcopy(verdict)
    client = client_for(mode, text)
    reply = build_reply(verdict, parsed, BedrockExplainer(client=client),
                        [n for n in notes if isinstance(n, str)])
    assert isinstance(reply, str)
    if code != "CONFIRMED":
        assert reply.endswith(CHECK_REMINDER)
        assert reply.count(CHECK_REMINDER) == 1
    assert verdict.code == snapshot.code
    assert verdict.reasons == snapshot.reasons
