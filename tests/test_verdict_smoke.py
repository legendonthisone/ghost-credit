"""Smoke checks for the verdict module: imports, forbidden names, Explainer shape."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

import ghost_credit.verdict as verdict_module
from ghost_credit.parser import ParsedAlert
from ghost_credit.paystack import PaystackResult
from ghost_credit.pattern_network import LookupResult, Verdict
from ghost_credit.verdict import Explainer, TemplateExplainer

SOURCE = Path(verdict_module.__file__).read_text(encoding="utf-8")


def test_types_are_imported_not_defined() -> None:
    """**Validates: Requirements 9.4**"""
    assert verdict_module.Verdict is Verdict
    assert verdict_module.LookupResult is LookupResult
    assert verdict_module.ParsedAlert is ParsedAlert
    assert verdict_module.PaystackResult is PaystackResult
    for name in ("Verdict", "LookupResult", "ParsedAlert", "PaystackResult"):
        assert not re.search(rf"^class {name}\b", SOURCE, re.MULTILINE)


@pytest.mark.parametrize(
    "pattern",
    [
        r"\b(openai|anthropic|claude|gpt|gemini|bedrock)\b",
        r"^\s*(import|from)\s+(requests|httpx|urllib|http|socket|aiohttp|random|time)\b",
        r"^\s*import\s+(datetime\.)?(time|random)\b",
        r"\bopen\(",
        r"\b(datetime\.now|datetime\.utcnow|date\.today)\b",
        r"sk_(test|live)_|pk_(test|live)_",
    ],
)
def test_source_has_no_forbidden_names(pattern: str) -> None:
    """**Validates: Requirements 4.1, 6.8, 9.1, 9.2**"""
    assert not re.search(pattern, SOURCE, re.IGNORECASE | re.MULTILINE)


def test_explainer_is_abstract_with_explain() -> None:
    """**Validates: Requirements 6.1**"""
    assert inspect.isabstract(Explainer)
    params = list(inspect.signature(Explainer.explain).parameters)
    assert params == ["self", "verdict", "parsed", "risk_notes"]
    assert not inspect.isabstract(TemplateExplainer)
