"""No key-like string may appear in source, tests or docs.

Validates: Requirement 3.3. Files named .env are skipped and never opened.
A failure reports only file names and counts, never the matched text.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("src", "tests", "docs")
SCAN_FILES = ("README.md", ".env.example", "pyproject.toml")
TEXT_SUFFIXES = {".py", ".md", ".toml", ".txt", ".json", ".example", ".cfg", ".ini"}
SKIP_DIRS = {"__pycache__", ".hypothesis", ".pytest_cache", ".git"}

# Key prefixes, split so this file does not match its own pattern.
_PREFIXES = ("sk_" + "live_", "sk_" + "test_", "pk_" + "live_", "pk_" + "test_", "AK" + "IA")
KEY_PATTERN = re.compile(
    "(?:" + "|".join(re.escape(p) for p in _PREFIXES) + r")[A-Za-z0-9]{10,}"
    + "|" + r"\bsk-[A-Za-z0-9_-]{20,}"
)


def _files_to_scan() -> list[Path]:
    """List the text files to scan, skipping any file named .env."""
    found: list[Path] = []
    for name in SCAN_DIRS:
        base = ROOT / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                found.append(path)
    for name in SCAN_FILES:
        path = ROOT / name
        if path.is_file():
            found.append(path)
    return [p for p in found if p.name != ".env"]


def test_no_key_like_strings_in_repo() -> None:
    """Report only the names of files with key-like text, not the text."""
    offenders: list[str] = []
    for path in _files_to_scan():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if KEY_PATTERN.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"key-like text found in {len(offenders)} file(s): {offenders}"


def test_scan_never_includes_env_files() -> None:
    """The scan list holds no file named .env."""
    assert all(p.name != ".env" for p in _files_to_scan())
