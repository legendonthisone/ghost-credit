"""Routes The Lab's three web addresses: /lab, /lab/data and /lab/check.

``route`` never raises. Every response it returns, success or error, carries
the same security headers. Checks run here always use ``TemplateExplainer``,
so The Lab never calls an AI model. The submitted text is never written into
any page.
"""

from __future__ import annotations

import html
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ghost_credit.lab import (
    ALLOWED_FIELDS,
    MAX_NEWEST,
    MAX_TRY_TEXT_CHARS,
    CheckStore,
    SlidingWindowLimiter,
    record_check,
    render_page,
)
from ghost_credit.pattern_network import NoopPatternNetwork
from ghost_credit.pipeline import make_paystack_verify, run_check
from ghost_credit.verdict import OWNER_LABELS, TemplateExplainer

__all__ = ["LabResponse", "route"]

LabResponse = tuple[int, dict[str, str], str]  # status, headers, body

CSP = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'"
SAMPLE_PATH = Path(__file__).with_name("lab_sample.json")

_log = logging.getLogger("ghost_credit.lab_router")


def _escape(value: object) -> str:
    """HTML-escape any value so it can only ever show up as plain text."""
    return html.escape(str(value), quote=True)


def _lab_headers(content_type: str) -> dict[str, str]:
    """Return the headers every Lab response must carry."""
    return {
        "Content-Type": content_type,
        "Content-Security-Policy": CSP,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }


def _json_body(data: object) -> str:
    """Write JSON with <, > and & escaped, so it can never read as HTML."""
    text = json.dumps(data)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _json(status: int, data: object) -> LabResponse:
    """A JSON response with the Lab headers."""
    return status, _lab_headers("application/json; charset=utf-8"), _json_body(data)


def _not_found() -> LabResponse:
    """The safe fallback: a plain 404 with the Lab headers."""
    return _json(404, {"error": "not found"})


def _load_sample() -> list[dict]:
    """Read the six synthetic sample records from the packaged file."""
    with SAMPLE_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, list) else []


def _only_allowed(record: object) -> dict:
    """Keep only the allowed fields of one stored record."""
    if not isinstance(record, dict):
        return {}
    return {name: record[name] for name in ALLOWED_FIELDS if name in record}


def _handle_data(store: CheckStore | None) -> LabResponse:
    """Return the newest records and the sample records."""
    records: list[dict] = []
    if store is not None:
        try:
            records = [_only_allowed(r) for r in store.newest(MAX_NEWEST) or []]
        except Exception as exc:  # noqa: BLE001 - a broken store must not break the page
            _log.warning("newest failed: %s", type(exc).__name__)
            records = []
    return _json(200, {"records": records, "sample": _load_sample()})


def _read_text(raw_body: object) -> str | None:
    """Return the ``text`` field of a JSON body, or None when it is unusable."""
    if not isinstance(raw_body, (bytes, bytearray)):
        return None
    try:
        data = json.loads(bytes(raw_body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    text = data.get("text") if isinstance(data, dict) else None
    return text if isinstance(text, str) else None


def _handle_check(
    raw_body: object,
    now: datetime,
    store: CheckStore | None,
    limiter: SlidingWindowLimiter,
    run_check_fn: Callable,
) -> LabResponse:
    """Check one pasted alert with the template explainer and log the result."""
    text = _read_text(raw_body)
    if text is None:
        return _json(400, {"error": "send JSON like {\"text\": \"...\"}"})
    if len(text) > MAX_TRY_TEXT_CHARS:
        return _json(413, {"error": "text is too long"})
    if not limiter.allow(now.timestamp()):
        return _json(429, {"error": "too many tries, wait a minute"})
    result = run_check_fn(
        text,
        None,
        None,
        None,
        now,
        explainer=TemplateExplainer(),
        paystack_verify=make_paystack_verify(),
        network=NoopPatternNetwork(),
    )
    record_check(store, result, "lab", now)
    code = result.verdict.code
    return _json(
        200,
        {
            "verdict": code,
            "owner_label": OWNER_LABELS.get(code, "UNVERIFIED"),
            "amount_kobo": result.parsed.amount_kobo,
            "red_flags": list(result.parsed.red_flags),
            "reasons": list(result.verdict.reasons),
            "risk_notes": list(result.risk_notes),
            "reply": result.reply,
        },
    )


def _normal_path(path: object) -> str:
    """Drop a trailing slash so /lab/ and /lab mean the same thing."""
    text = path if isinstance(path, str) else ""
    return text.rstrip("/") if len(text) > 1 else text


def route(
    method: object,
    path: object,
    query: object,
    headers: object,
    raw_body: object,
    *,
    now: datetime,
    store: CheckStore | None,
    limiter: SlidingWindowLimiter,
    run_check_fn: Callable[..., Any] = run_check,
) -> LabResponse:
    """Send a /lab request to its handler. Always returns a header-complete answer."""
    try:
        verb = method.upper() if isinstance(method, str) else ""
        where = _normal_path(path)
        allowed = {"/lab": "GET", "/lab/data": "GET", "/lab/check": "POST"}
        if where not in allowed:
            return _not_found()
        if verb != allowed[where]:
            return _json(405, {"error": "method not allowed"})
        if where == "/lab":
            return 200, _lab_headers("text/html; charset=utf-8"), render_page()
        if where == "/lab/data":
            return _handle_data(store)
        return _handle_check(raw_body, now, store, limiter, run_check_fn)
    except Exception as exc:  # noqa: BLE001 - never show a traceback to a visitor
        _log.warning("route failed: %s", type(exc).__name__)
        return _not_found()
