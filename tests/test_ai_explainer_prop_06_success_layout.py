"""Feature: ai-explainer, Property 6: Success layout is Headline, blank line, guarded text."""

from __future__ import annotations

from types import SimpleNamespace

from hypothesis import given, settings, strategies as st

from ai_explainer_helpers import FakeClient, codes, make_parsed, make_verdict
from ghost_credit.ai_explainer import BedrockExplainer, guard_output
from ghost_credit.verdict import CHECK_REMINDER, TemplateExplainer

_clean = st.sampled_from(["The date looks wrong.", "No balance line was found.", "Take extra care."])
_model_text = st.lists(st.sampled_from(["Please look closely. ", "Open your bank app. ",
                                        "Take your time!\n", "Wait a moment. "]),
                       min_size=1, max_size=6).map("".join)


# **Validates: Requirements 1.4, 1.5, 4.1, 4.2, 4.3**
@settings(max_examples=150, deadline=None)
@given(code=st.one_of(codes, st.just("WEIRD")), reasons=st.lists(_clean, min_size=1, max_size=3),
       notes=st.lists(_clean, max_size=3), text=_model_text)
def test_success_layout(code, reasons, notes, text) -> None:
    verdict = (make_verdict(code, reasons) if code != "WEIRD"
               else SimpleNamespace(code="WEIRD", reasons=reasons))
    parsed = make_parsed()
    client = FakeClient("reply", text=text)
    out = BedrockExplainer(client=client).explain(verdict, parsed, notes)
    template = TemplateExplainer().explain(verdict, parsed, notes)
    headline = template.split("\n", 1)[0]
    guarded = guard_output(text, code)
    assert guarded is not None
    assert out == f"{headline}\n\n{guarded}"
    assert out.startswith(headline + "\n\n")
    assert not out.endswith(CHECK_REMINDER)
    if code == "WEIRD":
        assert headline.startswith("UNVERIFIED")
