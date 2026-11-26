"""Smoke checks on the source text of whatsapp.py."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "src" / "ghost_credit" / "whatsapp.py"
TEXT = SOURCE.read_text(encoding="utf-8")
TREE = ast.parse(TEXT)


def _imported_roots() -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(TREE):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_imports_only_standard_library_and_ghost_credit() -> None:
    allowed = set(sys.stdlib_module_names) | {"ghost_credit"}
    assert _imported_roots() <= allowed


def test_uses_constant_time_compare() -> None:
    assert "hmac.compare_digest" in TEXT


def test_has_no_open_call_and_no_model_names() -> None:
    calls = [n for n in ast.walk(TREE) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "open"]
    assert calls == []
    for word in ("bedrock", "boto3", "openai", "anthropic", "nova"):
        assert word not in TEXT.lower()


def test_graph_api_version_is_defined_once() -> None:
    assert TEXT.count("GRAPH_API_VERSION =") == 1
    assert "v21.0" in TEXT and TEXT.count("v21.0") == 1


def test_sender_id_is_none_in_the_check_call() -> None:
    assert "        None,\n        None,\n        category," in TEXT


def test_docstring_says_dedupe_is_best_effort() -> None:
    doc = ast.get_docstring(TREE) or ""
    assert "best effort" in doc and "Lambda container" in doc
