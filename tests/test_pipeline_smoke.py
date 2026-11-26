"""Smoke checks on the source of pipeline.py."""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

from ghost_credit import pipeline

SOURCE = Path(pipeline.__file__).read_text(encoding="utf-8")
BANNED_MODULES = {"requests", "httpx", "urllib", "urllib3", "http", "socket", "aiohttp",
                  "openai", "anthropic", "boto3"}
BANNED_WORDS = ["openai", "anthropic", "claude", "gpt-", "gemini", "bedrock"]


def _imported_roots() -> set[str]:
    """Return the top-level names of every import in the module."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(SOURCE)):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_ai_http_or_socket_imports() -> None:
    """No AI client, HTTP library or socket is imported."""
    assert not (_imported_roots() & BANNED_MODULES)


def test_no_ai_names_open_float_or_secrets() -> None:
    """No AI model name, open() call, float use or key-like text in the source."""
    lowered = SOURCE.lower()
    for word in BANNED_WORDS:
        assert word not in lowered
    assert not re.search(r"\bopen\s*\(", SOURCE)
    assert not re.search(r"\bfloat\b", SOURCE)
    assert not re.search(r"\b[sp]k_(test|live)_", SOURCE)


def test_run_check_parameter_order() -> None:
    """Positional parameters first, then the four keyword-only ones."""
    params = list(inspect.signature(pipeline.run_check).parameters.values())
    names = [p.name for p in params]
    assert names == ["text", "sender_id", "image_bytes", "merchant_category", "now",
                     "reader", "paystack_verify", "network", "explainer", "used_references"]
    assert all(p.kind is p.KEYWORD_ONLY for p in params[5:])


def test_no_module_level_name_holds_image_bytes() -> None:
    """No module variable keeps bytes."""
    for name, value in vars(pipeline).items():
        assert not isinstance(value, (bytes, bytearray)), name
