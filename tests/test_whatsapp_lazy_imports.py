"""Example tests: image libraries load lazily in screenshot.py.

Requirements 10.1 to 10.5.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

from ghost_credit import screenshot

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# Makes every import of the four image libraries fail, like the Lambda zip.
BLOCKER = """
import sys

class Block:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("PIL", "imagehash", "numpy", "scipy"):
            raise ImportError("blocked: " + name)
        return None

sys.meta_path.insert(0, Block())
"""


def _run(code: str) -> subprocess.CompletedProcess:
    """Run code in a fresh Python with the libraries blocked."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    env["PATTERN_NETWORK"] = "off"
    return subprocess.run(
        [sys.executable, "-c", BLOCKER + code],
        capture_output=True, text=True, env=env, timeout=60,
    )


def test_pipeline_imports_without_image_libraries() -> None:
    result = _run("import ghost_credit.pipeline\nprint('imported')")
    assert result.returncode == 0, result.stderr[-500:]
    assert "imported" in result.stdout


def test_phash_is_none_when_libraries_missing() -> None:
    result = _run(
        "from ghost_credit.screenshot import _compute_phash\n"
        "print(_compute_phash(b'abc'))"
    )
    assert result.returncode == 0, result.stderr[-500:]
    assert result.stdout.strip() == "None"


def test_module_attributes_are_readable() -> None:
    assert hasattr(screenshot.Image, "open")
    assert hasattr(screenshot.imagehash, "phash")


def test_monkeypatching_image_open_still_works(monkeypatch) -> None:
    from PIL import Image

    monkeypatch.setattr(screenshot.Image, "open", lambda *a, **k: "patched")
    assert Image.open(b"x") == "patched"


def test_unknown_attribute_raises_attribute_error() -> None:
    try:
        screenshot.not_a_real_name  # noqa: B018
    except AttributeError:
        return
    raise AssertionError("expected AttributeError")


def test_no_top_level_image_imports_in_source() -> None:
    tree = ast.parse((SRC / "ghost_credit" / "screenshot.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] in ("PIL", "imagehash") for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in ("PIL", "imagehash")
