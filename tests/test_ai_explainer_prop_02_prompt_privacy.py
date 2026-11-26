"""Feature: ai-explainer, Property 2: The Prompt holds only clean reasons and notes."""

from __future__ import annotations

import re

from hypothesis import given, settings, strategies as st

from ai_explainer_helpers import (SENSITIVE_SNIPPETS, SYNTH_ACCOUNT, SYNTH_NARRATION, FakeClient,
                                  codes, make_parsed, make_verdict, notes_list, reasons_list)
from ghost_credit.ai_explainer import (MAX_ITEM_CHARS, SYSTEM_INSTRUCTION, BedrockExplainer,
                                       _sensitive_values)
from ghost_credit.verdict import OWNER_LABELS, TemplateExplainer


def _user_text(call: dict) -> str:
    return call["messages"][0]["content"][0]["text"]


# **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.6**
@settings(max_examples=200, deadline=None)
@given(code=codes, reasons=reasons_list, notes=notes_list)
def test_prompt_holds_only_clean_items(code, reasons, notes) -> None:
    verdict = make_verdict(code, reasons)
    parsed = make_parsed()
    client = FakeClient("reply", text="Take care with this alert.")
    BedrockExplainer(client=client).explain(verdict, parsed, notes)
    if not client.calls:
        return
    call = client.calls[0]
    user = _user_text(call)
    prompt = (SYSTEM_INSTRUCTION + "\n" + user).lower()

    for bad in _sensitive_values(verdict, parsed) + [s.lower() for s in SENSITIVE_SNIPPETS]:
        assert bad not in user.lower()
    assert not re.search(r"\d{7,}", re.sub(r"(?<=\d)[ ,.\-](?=\d)", "", prompt))
    headline = TemplateExplainer().explain(verdict, parsed, notes).split("\n", 1)[0]
    assert headline not in user
    for label in OWNER_LABELS.values():
        assert label.lower() not in prompt
    assert SYNTH_ACCOUNT not in user and SYNTH_NARRATION not in user

    lines = user.split("\n")
    assert lines[0] == "Points:"
    bullets = [line[2:] for line in lines[1:]]
    assert all(line.startswith("- ") for line in lines[1:])
    assert 1 <= len(bullets) <= 6
    assert all(0 < len(b) <= MAX_ITEM_CHARS for b in bullets)

    # Order: first 3 clean reasons, then first 3 clean notes, original order kept.
    sensitive = _sensitive_values(verdict, parsed)

    def accept(items: list) -> list[str]:
        ok = [i.strip()[:MAX_ITEM_CHARS] for i in items
              if isinstance(i, str) and i.strip()
              and not any(s in i.lower() for s in sensitive)
              and not re.search(r"\d{7,}", re.sub(r"(?<=\d)[ ,.\-](?=\d)", "", i))]
        return ok[:3]

    assert bullets == accept(reasons) + accept(notes)
