"""Manual Paystack smoke check. Run it yourself: python scripts/paystack_smoke.py

It reads PAYSTACK_SECRET_KEY from the environment, or from a .env file in the
project root, and asks Paystack about a made-up reference. It prints only the
status and the reason. It never prints the key.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ghost_credit.parser import ParsedAlert  # noqa: E402
from ghost_credit.paystack import verify  # noqa: E402

KEY_NAME = "PAYSTACK_SECRET_KEY"
SMOKE_REFERENCE = "GC-SMOKE-0001"
LAGOS = timezone(timedelta(hours=1))


def read_env_file(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE lines from a .env file, without any extra library."""
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[name.strip()] = value
    return values


def find_key() -> str | None:
    """Return the key from the environment first, then from the .env file."""
    key = os.environ.get(KEY_NAME)
    if key:
        return key
    return read_env_file(PROJECT_ROOT / ".env").get(KEY_NAME) or None


def main() -> int:
    """Check a made-up reference and print only the status and the reason."""
    parsed = ParsedAlert(amount_kobo=100, claimed_reference=SMOKE_REFERENCE)
    result = verify(parsed, find_key(), datetime.now(LAGOS))
    print(f"status: {result.status}")
    print(f"reason: {result.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())