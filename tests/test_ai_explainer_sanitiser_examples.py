"""Examples for the AI explainer prompt sanitiser and packaging."""

from __future__ import annotations

import re
from pathlib import Path

from ai_explainer_helpers import make_parsed, make_verdict
from ghost_credit import ai_explainer as ae

ROOT = Path(__file__).resolve().parent.parent


def test_sensitive_items_are_dropped_and_order_kept() -> None:
    verdict = make_verdict("SUSPICIOUS", [
        "First clean reason.",
        "Mentions DATE_ODD inside.",
        "Account 012****789 appears.",
        "Amount 4500000 appears.",
        "Call 0801 234 5678 now.",
        "Second clean reason.",
    ])
    items = ae._prompt_items(verdict, make_parsed(), ["A clean note."])
    assert items == ["First clean reason.", "Second clean reason.", "A clean note."]


def test_caps_three_reasons_three_notes_and_160_chars() -> None:
    verdict = make_verdict("UNVERIFIED", [f"Reason {c}." for c in "abcde"])
    notes = ["x" * 400, "n2", "n3", "n4"]
    items = ae._prompt_items(verdict, make_parsed(), notes)
    assert items[:3] == ["Reason a.", "Reason b.", "Reason c."]
    assert items[3:] == ["x" * 160, "n2", "n3"]


def test_non_string_and_non_list_inputs_give_nothing() -> None:
    verdict = make_verdict("UNVERIFIED", [1, None])
    assert ae._prompt_items(verdict, None, "not a list") == []


def test_instruction_has_rules_and_no_sensitive_words() -> None:
    text = ae.SYSTEM_INSTRUCTION.lower()
    assert "2 short sentences" in text
    assert "accuse" in text
    assert "proves money is real" in text
    assert "legal advice" in text
    assert "whether to release goods" in text
    for word in ("confirmed", "not_found", "suspicious", "unverified", "ghost", "alive"):
        assert word not in text
    for code in ae.RED_FLAG_CODES:
        assert code.lower() not in text


def test_boto3_only_in_aws_extra() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    deps = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    assert "boto3" not in deps
    assert re.search(r'(?m)^aws\s*=\s*\["boto3"\]', text)


def test_env_example_has_empty_explainer() -> None:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert "EXPLAINER=" in [line.strip() for line in lines]


def test_module_source_has_no_key_like_strings() -> None:
    source = (ROOT / "src" / "ghost_credit" / "ai_explainer.py").read_text(encoding="utf-8")
    assert not re.search(r"AKIA[0-9A-Z]{8,}|ASIA[0-9A-Z]{8,}|aws_secret|aws_session_token|sk_(test|live)_", source, re.I)
