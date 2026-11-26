"""Feature: ai-explainer, Property 1: Explain never raises and changes nothing."""

from __future__ import annotations

import copy
from types import SimpleNamespace

from hypothesis import given, settings, strategies as st

from ai_explainer_helpers import (client_for, client_modes, make_parsed, make_verdict,
                                  notes_list, reasons_list)
from ghost_credit.ai_explainer import BedrockExplainer

_verdicts = st.one_of(
    st.builds(make_verdict, st.sampled_from(["CONFIRMED", "NOT_FOUND", "SUSPICIOUS", "UNVERIFIED"]),
              reasons_list),
    st.builds(lambda c, r: SimpleNamespace(code=c, reasons=r),
              st.one_of(st.text(max_size=8), st.none(), st.integers()),
              st.one_of(reasons_list, st.none(), st.text(max_size=5))),
)
_parsed = st.one_of(st.none(), st.just(make_parsed()), st.just(object()),
                    st.just(SimpleNamespace(red_flags=5, amount_kobo=True, narration=7)))


# **Validates: Requirements 1.3, 6.6**
@settings(max_examples=150, deadline=None)
@given(verdict=_verdicts, parsed=_parsed, notes=notes_list, mode=client_modes,
       text=st.text(max_size=300))
def test_explain_never_raises_and_changes_nothing(verdict, parsed, notes, mode, text) -> None:
    client = client_for(mode, text)
    before = (copy.deepcopy(verdict), copy.deepcopy(parsed), copy.deepcopy(notes))
    out = BedrockExplainer(client=client).explain(verdict, parsed, notes)
    assert isinstance(out, str)
    assert verdict == before[0] and notes == before[2]
    if hasattr(parsed, "__dataclass_fields__"):
        assert parsed == before[1]
    assert len(client.calls) <= 1
