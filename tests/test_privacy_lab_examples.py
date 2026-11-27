"""Example tests: PRIVACY.md states what The Lab keeps."""

from __future__ import annotations

import re
from pathlib import Path

PRIVACY = (Path(__file__).resolve().parents[1] / "PRIVACY.md").read_text(encoding="utf-8")


def _keep_section() -> str:
    match = re.search(r"## What we keep\n(.*?)\n## ", PRIVACY, re.S)
    assert match, "missing 'What we keep' section"
    return match.group(1)


def test_states_30_day_lab_retention_of_results() -> None:
    section = _keep_section()
    assert "The Lab" in section and "30 days" in section
    for word in ("verdict", "amount", "red flags", "reasons"):
        assert word in section


def test_states_text_and_phone_numbers_never_stored() -> None:
    assert "Message text and phone numbers are never stored" in _keep_section()
