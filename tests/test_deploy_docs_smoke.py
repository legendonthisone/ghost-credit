"""Smoke checks for docs/deploy.md and .env.example."""

from __future__ import annotations

import re
from pathlib import Path

from deploy_helpers import load_deploy_module

ROOT = Path(__file__).resolve().parents[1]
GUIDE = (ROOT / "docs" / "deploy.md").read_text(encoding="utf-8")


def test_guide_has_numbered_steps_and_commands() -> None:
    """The guide has numbered steps and the key commands."""
    assert re.search(r"^## 1\. ", GUIDE, re.M)
    assert re.search(r"^## 8\. ", GUIDE, re.M)
    assert "python scripts\\deploy_lambda.py --dry-run" in GUIDE
    assert re.search(r"^python scripts\\deploy_lambda\.py$", GUIDE, re.M)
    assert "messages" in GUIDE and "Function URL" in GUIDE


def test_guide_states_the_required_notes() -> None:
    """boto3, durable-store and approval notes are present."""
    assert "ships `boto3`" in GUIDE and "no layer is needed" in GUIDE
    assert "durable store" in GUIDE and "needs approval" in GUIDE
    assert "Ayobami approves" in GUIDE


def test_guide_holds_no_email_or_key() -> None:
    """No email address and no key-like value."""
    assert "@" not in GUIDE
    assert not re.search(r"sk_(test|live)_|pk_(test|live)_", GUIDE)
    assert not re.search(r"\bAKIA[0-9A-Z]{8,}", GUIDE)


def test_env_example_lists_every_name_empty() -> None:
    """Every Lambda variable name is in .env.example with an empty value."""
    deploy = load_deploy_module()
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    pairs = [line.split("=", 1) for line in lines if "=" in line]
    found = {name.strip(): value.strip() for name, value in pairs}
    for name in deploy.LAMBDA_VARIABLE_NAMES:
        assert name in found and found[name] == ""
    assert [n for n, _ in pairs].count("EXPLAINER") == 1
