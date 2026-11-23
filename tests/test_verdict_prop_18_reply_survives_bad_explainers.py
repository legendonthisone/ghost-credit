"""Feature: verdict-engine, Property 18: build_reply keeps the verdict and survives bad Explainers."""

from __future__ import annotations

import copy

from hypothesis import given, settings, strategies as st

from ghost_credit.verdict import (
    CHECK_REMINDER,
    CONFIRMED,
    Explainer,
    build_reply,
    decide,
)
from verdict_helpers import lookup_results, parsed_alerts, paystack_inputs


class _Bad(Explainer):
    """Returns a given value, raises, or tries to change the verdict it gets."""

    def __init__(self, mode: str, value: object = None) -> None:
        self.mode, self.value = mode, value

    def explain(self, verdict, parsed, risk_notes):  # type: ignore[no-untyped-def]
        if self.mode == "raise":
            raise RuntimeError("boom")
        if self.mode == "mutate":
            verdict.code = "CONFIRMED"
            verdict.reasons.append("changed")
            return "mutated text"
        return self.value


explainers = st.one_of(
    st.builds(_Bad, st.just("raise")),
    st.builds(_Bad, st.just("mutate")),
    st.builds(_Bad, st.just("value"), st.one_of(st.none(), st.integers(), st.sampled_from(["", "  \n"]))),
    st.builds(_Bad, st.just("value"), st.text(max_size=40)),
)
notes_st = st.lists(st.text(min_size=1, max_size=30), max_size=3)


@settings(max_examples=100)
@given(parsed=parsed_alerts, paystack=paystack_inputs, lookup=lookup_results,
       explainer=explainers, notes=notes_st)
def test_reply_survives_bad_explainers(parsed, paystack, lookup, explainer, notes) -> None:
    """**Validates: Requirements 6.9, 6.10, 6.11**"""
    verdict = decide(parsed, paystack, lookup)
    before = copy.deepcopy(verdict)
    reply = build_reply(verdict, parsed, explainer, notes)
    assert isinstance(reply, str)
    assert verdict == before
    failed = explainer.mode == "raise" or (
        explainer.mode == "value"
        and (not isinstance(explainer.value, str) or not explainer.value.strip())
    )
    if failed:
        expected = "\n".join([" ".join(verdict.reasons), *notes])
        if verdict.code != CONFIRMED:
            expected = expected.rstrip()
            expected = f"{expected}\n{CHECK_REMINDER}" if expected else CHECK_REMINDER
        assert reply == expected
