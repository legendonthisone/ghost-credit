"""Smoke checks for the Paystack verifier's module conventions.

Validates: Requirements 1.3, 1.7, 6.4, 8.1, 8.2, 8.3, 8.4, 9.3, 9.4, 9.5.
The real default_http is never called here.
"""

from __future__ import annotations

import ast
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from ghost_credit import paystack
from ghost_credit.parser import ParsedAlert

PAYSTACK_PATH = Path(paystack.__file__)
_FAKE_KEY = "sk_" + "test_" + "smokecheck"


def _imported_modules() -> list[tuple[str, int]]:
    """List (module name, relative level) for each import in paystack.py."""
    tree = ast.parse(PAYSTACK_PATH.read_text(encoding="utf-8"))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append((node.module or "", node.level))
    return found


def test_http_none_selects_default_http(monkeypatch) -> None:
    """With http=None, verify calls the module's default_http (replaced by a stand-in)."""
    calls: list[str] = []

    def stand_in(url, headers, timeout_seconds):
        calls.append(url)
        return 200, json.dumps({"data": []}).encode("utf-8")

    monkeypatch.setattr(paystack, "default_http", stand_in)
    parsed = ParsedAlert.__new__(ParsedAlert)
    object.__setattr__(parsed, "amount_kobo", 4500000)
    result = paystack.verify(parsed, _FAKE_KEY, datetime(2026, 11, 20, 10, 0, 0))
    assert len(calls) == 1
    assert result.status == "NOT_FOUND" and result.checked is True


def test_parsed_alert_comes_from_parser() -> None:
    """ParsedAlert is imported from ghost_credit.parser, not redefined."""
    assert paystack.ParsedAlert is ParsedAlert
    assert ("ghost_credit.parser", 0) in _imported_modules()
    tree = ast.parse(PAYSTACK_PATH.read_text(encoding="utf-8"))
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    assert "ParsedAlert" not in classes


def test_module_imports_only_standard_library() -> None:
    """Every import is standard library, or ghost_credit.parser."""
    for name, level in _imported_modules():
        assert level == 0
        top = name.split(".")[0]
        assert top in sys.stdlib_module_names or name == "ghost_credit.parser", name


def test_pattern_network_is_off() -> None:
    """The suite runs with PATTERN_NETWORK off (unset counts as the default, off)."""
    assert os.environ.get("PATTERN_NETWORK", "off").lower() == "off"


def test_source_has_no_key_prefix_literal() -> None:
    """paystack.py never holds the full test key prefix as one literal."""
    assert ("sk_" + "test_") not in PAYSTACK_PATH.read_text(encoding="utf-8")
