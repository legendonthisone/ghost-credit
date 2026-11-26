"""Examples for the tightened AI instruction, the guard and the already-used headline."""

from __future__ import annotations

import pytest

from ghost_credit.ai_explainer import SYSTEM_INSTRUCTION, guard_output
from ghost_credit.paystack import REASON_ALREADY_USED
from ghost_credit.verdict import NOT_FOUND, TemplateExplainer, _make_verdict


@pytest.mark.parametrize(
    "text",
    [
        "We are looking into it.",
        "Someone is investigating this alert.",
        "The investigation will take a day.",
        "We'll update you soon.",
        "Our team will help.",
        "We checked it.",
    ],
)
def test_guard_rejects_investigating_and_we_wording(text: str) -> None:
    assert guard_output(text, NOT_FOUND) is None


def test_guard_keeps_plain_owner_text() -> None:
    text = "Paystack has no record of this alert. Hold the goods for now."
    assert guard_output(text, NOT_FOUND) == text


def test_instruction_asks_two_sentences_and_forbids_we_and_follow_up() -> None:
    text = SYSTEM_INSTRUCTION.lower()
    assert "2 short sentences" in text
    assert "never say 'we'" in text
    assert "investigating" in text
    assert "follow-up" in text


def test_already_used_headline_is_exact() -> None:
    verdict = _make_verdict(NOT_FOUND, True, [REASON_ALREADY_USED])
    first = TemplateExplainer().explain(verdict, None, []).split("\n")[0]
    assert first == "GHOST. Hold the goods. This payment was already used."
