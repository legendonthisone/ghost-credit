"""The Lab: anonymised check log, rate limiter and the dashboard page.

Privacy comes first. A saved record holds only verdict-level facts. The
sanitiser runs inside ``record_check``, before any store sees the record, so a
badly written store can never keep message text, phone numbers, names,
account digits or references. Saving is best effort and never changes a reply.

``boto3`` is imported only inside the DynamoDB methods, never at import time.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from ghost_credit.pipeline import FLAG_ORDER, LAGOS
from ghost_credit.verdict import FLAG_REASONS, OWNER_LABELS

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ghost_credit.pipeline import CheckResult

__all__ = [
    "ALLOWED_FIELDS",
    "TTL_SECONDS",
    "MAX_LIST_ITEMS",
    "MAX_TEXT_FIELD_CHARS",
    "MAX_BANK_CHARS",
    "MAX_TRY_TEXT_CHARS",
    "RATE_LIMIT_PER_MINUTE",
    "CheckStore",
    "InMemoryCheckStore",
    "DynamoCheckStore",
    "get_store",
    "sanitise_record",
    "record_check",
    "SlidingWindowLimiter",
    "format_naira",
    "plain_english_flags",
    "render_page",
]

ALLOWED_FIELDS = (
    "check_id",
    "checked_at",
    "channel",
    "verdict",
    "owner_label",
    "amount_kobo",
    "claimed_bank",
    "red_flags",
    "reasons",
    "risk_notes",
    "expires_at",
)
TTL_SECONDS = 30 * 24 * 60 * 60
MAX_LIST_ITEMS = 10
MAX_TEXT_FIELD_CHARS = 120
MAX_BANK_CHARS = 60
MAX_TRY_TEXT_CHARS = 2000
RATE_LIMIT_PER_MINUTE = 20
MAX_NEWEST = 50
DEFAULT_TABLE = "ghost-credit-checks"
REMOVED = "[removed]"

# Fields the sanitiser leaves alone: ids and a timestamp that we build ourselves.
_UNMASKED_FIELDS = ("check_id", "checked_at")
_LIST_FIELDS = ("red_flags", "reasons", "risk_notes")

# A run of 7 or more digits, optionally split by spaces, hyphens, dots or commas.
_DIGIT_RUN = re.compile(r"\d(?:[ \-.,]*\d){6,}")

_log = logging.getLogger("ghost_credit.lab")


# --- Storage --------------------------------------------------------------


class CheckStore(Protocol):
    """Where anonymised check records are kept."""

    def save(self, record: dict) -> None:
        """Keep one record."""
        ...

    def newest(self, limit: int) -> list[dict]:
        """Return up to ``limit`` records, newest first."""
        ...


class InMemoryCheckStore:
    """Keeps records in memory for the life of the process (used by tests)."""

    def __init__(self) -> None:
        self._records: list[dict] = []
        self._lock = threading.Lock()

    def save(self, record: dict) -> None:
        """Keep a copy of the record."""
        with self._lock:
            self._records.append(copy.deepcopy(record))

    def newest(self, limit: int) -> list[dict]:
        """Return up to ``limit`` records, most recently saved first."""
        if not isinstance(limit, int) or limit <= 0:
            return []
        with self._lock:
            return copy.deepcopy(self._records[::-1][:limit])


def _encode_value(value: Any) -> dict:
    """Turn one Python value into its DynamoDB typed form."""
    if value is None:
        return {"NULL": True}
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, int):
        return {"N": str(value)}
    if isinstance(value, list):
        return {"L": [{"S": str(item)} for item in value]}
    return {"S": str(value)}


def _decode_value(typed: Any) -> Any:
    """Turn one DynamoDB typed value back into a Python value."""
    if not isinstance(typed, dict):
        return None
    if "S" in typed:
        return typed["S"]
    if "N" in typed:
        return int(typed["N"])
    if "L" in typed:
        return [_decode_value(item) for item in typed["L"]]
    if "BOOL" in typed:
        return typed["BOOL"]
    return None


class DynamoCheckStore:
    """Keeps records in the Checks_Table. ``boto3`` is loaded only when used."""

    def __init__(self, table_name: str | None = None, client: Any = None) -> None:
        self._table = table_name or os.environ.get("CHECKS_TABLE") or DEFAULT_TABLE
        self._client = client

    def _get_client(self) -> Any:
        """Return the DynamoDB client, creating it on first use."""
        if self._client is None:
            import boto3  # lazy: tests and the webhook never need it

            self._client = boto3.client("dynamodb")
        return self._client

    def save(self, record: dict) -> None:
        """Write the record with exactly one PutItem call."""
        item = {name: _encode_value(value) for name, value in record.items()}
        self._get_client().put_item(TableName=self._table, Item=item)

    def newest(self, limit: int) -> list[dict]:
        """Scan once, sort by ``checked_at`` descending, return at most 50."""
        response = self._get_client().scan(TableName=self._table)
        items = response.get("Items", []) if isinstance(response, dict) else []
        records = [
            {name: _decode_value(typed) for name, typed in item.items()}
            for item in items
        ]
        records.sort(key=lambda r: str(r.get("checked_at") or ""), reverse=True)
        count = max(0, min(limit, MAX_NEWEST))
        return records[:count]


def get_store() -> CheckStore | None:
    """Return a DynamoCheckStore when CHECKS_TABLE is set, else None."""
    if os.environ.get("CHECKS_TABLE"):
        return DynamoCheckStore()
    return None


# --- Sanitiser ------------------------------------------------------------


def _mask_digits(text: str) -> str:
    """Replace every run of 7 or more digits with ``[removed]``."""
    return _DIGIT_RUN.sub(REMOVED, text)


def _clean_text(value: Any, limit: int | None = None) -> str:
    """Make one value safe text: mask long digit runs, then cut the length.

    Why mask first: cutting first could leave a partial digit run behind.
    """
    text = _mask_digits(str(value))
    return text if limit is None else text[:limit]


def _clean_list(value: Any, cap_items: int, limit: int | None) -> list[str]:
    """Clean a list of strings, keeping at most ``cap_items`` entries."""
    if not isinstance(value, (list, tuple)):
        return []
    return [_clean_text(item, limit) for item in list(value)[:cap_items]]


def sanitise_record(record: dict) -> dict:
    """Keep only the allowed fields, mask long digit runs and cut lengths.

    Why: this is the privacy guard. Whatever a caller puts in, nothing but
    verdict-level text and numbers can come out.
    """
    clean: dict = {}
    for name in ALLOWED_FIELDS:
        if name not in record:
            continue
        value = record[name]
        if name in _LIST_FIELDS:
            limit = MAX_TEXT_FIELD_CHARS if name != "red_flags" else None
            clean[name] = _clean_list(value, MAX_LIST_ITEMS, limit)
        elif name == "claimed_bank":
            clean[name] = None if value is None else _clean_text(value, MAX_BANK_CHARS)
        elif name in ("amount_kobo", "expires_at"):
            ok = isinstance(value, int) and not isinstance(value, bool)
            clean[name] = value if ok else None
        elif name in _UNMASKED_FIELDS:
            clean[name] = str(value)
        else:
            clean[name] = _clean_text(value)
    return clean


# --- Record builder -------------------------------------------------------


def _lagos_time(now: datetime) -> datetime:
    """Return ``now`` in Lagos time; a naive time counts as Lagos already."""
    if now.tzinfo is None or now.utcoffset() is None:
        return now.replace(tzinfo=LAGOS, microsecond=0)
    return now.astimezone(LAGOS).replace(microsecond=0)


def _build_record(check_result: "CheckResult", channel: str, now: datetime) -> dict:
    """Build the raw record from a CheckResult. Only verdict-level fields."""
    moment = _lagos_time(now)
    code = check_result.verdict.code
    parsed = check_result.parsed
    return {
        "check_id": check_result.check_id,
        "checked_at": moment.isoformat(timespec="seconds"),
        "channel": channel,
        "verdict": code,
        "owner_label": OWNER_LABELS.get(code, "UNVERIFIED"),
        "amount_kobo": parsed.amount_kobo,
        "claimed_bank": parsed.claimed_bank,
        "red_flags": list(parsed.red_flags),
        "reasons": list(check_result.verdict.reasons),
        "risk_notes": list(check_result.risk_notes),
        "expires_at": int(moment.timestamp()) + TTL_SECONDS,
    }


def record_check(
    store: CheckStore | None,
    check_result: "CheckResult",
    channel: str,
    now: datetime,
) -> None:
    """Build, sanitise and save one record. It never raises.

    Why: logging is a side job. A failure here must never change the reply
    the owner gets. Only the error type name is logged.
    """
    if store is None:
        return
    try:
        record = sanitise_record(_build_record(check_result, channel, now))
        store.save(record)
    except Exception as exc:  # noqa: BLE001 - best effort by design
        _log.warning("record_check failed: %s", type(exc).__name__)


# --- Rate limiter ---------------------------------------------------------


class SlidingWindowLimiter:
    """Allow at most ``limit`` calls in any rolling ``window_seconds``."""

    def __init__(
        self, limit: int = RATE_LIMIT_PER_MINUTE, window_seconds: float = 60.0
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._times: list[float] = []
        self._lock = threading.Lock()

    def allow(self, now: float) -> bool:
        """Say whether a call at time ``now`` is within the limit, and count it."""
        with self._lock:
            self._times = [t for t in self._times if now - self._window < t <= now]
            if len(self._times) >= self._limit:
                return False
            self._times.append(now)
            return True


# --- Small helpers --------------------------------------------------------


def format_naira(amount_kobo: int | None) -> str:
    """Write kobo as naira using whole-number maths only: 4500000 -> NGN 45,000.00."""
    if isinstance(amount_kobo, bool) or not isinstance(amount_kobo, int):
        return "Amount not read"
    sign = "-" if amount_kobo < 0 else ""
    naira, kobo = divmod(abs(amount_kobo), 100)
    return f"{sign}NGN {naira:,}.{kobo:02d}"


def plain_english_flags(codes: list[str]) -> list[str]:
    """Map red flag codes to everyday sentences; unknown codes are dropped."""
    return [FLAG_REASONS[c] for c in codes if isinstance(c, str) and c in FLAG_REASONS]


# --- Page -----------------------------------------------------------------

_PAGE_CSS = """
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#14121f;color:#f2f0fa;line-height:1.45}
header{padding:20px 16px 8px}
h1{margin:0;font-size:1.6rem}
.sub{margin:4px 0 0;color:#cfc9e6}
main{padding:8px 16px 40px;max-width:760px;margin:0 auto}
.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:12px 0}
label{font-size:1rem}
select,button,textarea{font:inherit;min-height:44px;border-radius:8px;border:1px solid #6b6393;background:#1f1b33;color:#f2f0fa;padding:8px 12px}
button{background:#ff8a1f;color:#1a1200;font-weight:700;border:0;cursor:pointer}
textarea{width:100%;box-sizing:border-box;min-height:110px}
input[type=checkbox]{width:24px;height:24px;vertical-align:middle}
.card{border-radius:12px;padding:14px;margin:12px 0;border:2px solid}
.card h2{margin:0 0 6px;font-size:1.2rem}
.card ul{margin:6px 0 0;padding-left:20px}
.tag{display:inline-block;font-size:.8rem;border-radius:6px;padding:1px 8px;margin-left:8px;background:#000;color:#fff}
.alive{background:#e7ffe9;color:#06280d;border-color:#0f9d2e}
.ghost{background:#d9d7e6;color:#26233a;border:2px dashed #6b6393;opacity:.9}
.suspicious{background:#fff1d6;color:#3a2300;border-color:#d97706}
.unverified{background:#e6e9f2;color:#1b2233;border-color:#64748b}
.empty{color:#cfc9e6}
#result{margin-top:12px}
pre{white-space:pre-wrap;margin:6px 0 0;font:inherit}
"""

_PAGE_JS = r"""
(function () {
  var FLAGS = __FLAGS__;
  var LABELS = ["ALIVE", "GHOST", "SUSPICIOUS", "UNVERIFIED"];
  var state = { records: [], sample: [], showSample: false, touched: false, filter: "ALL" };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) { node.className = cls; }
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    return node;
  }

  function clear(node) {
    while (node.firstChild) { node.removeChild(node.firstChild); }
  }

  function pad2(n) { return n < 10 ? "0" + n : String(n); }

  function naira(kobo) {
    if (typeof kobo !== "number" || kobo !== Math.floor(kobo)) { return "Amount not read"; }
    var whole = Math.floor(Math.abs(kobo) / 100);
    var rest = Math.abs(kobo) % 100;
    var text = String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return (kobo < 0 ? "-" : "") + "NGN " + text + "." + pad2(rest);
  }

  function addList(card, title, items) {
    if (!items || !items.length) { return; }
    card.appendChild(el("strong", null, title));
    var ul = el("ul");
    items.forEach(function (item) { ul.appendChild(el("li", null, item)); });
    card.appendChild(ul);
  }

  function flagSentences(codes) {
    var out = [];
    (codes || []).forEach(function (code) {
      if (Object.prototype.hasOwnProperty.call(FLAGS, code)) { out.push(FLAGS[code]); }
    });
    return out;
  }

  function buildCard(record, isSample) {
    var label = LABELS.indexOf(record.owner_label) >= 0 ? record.owner_label : "UNVERIFIED";
    var card = el("article", "card " + label.toLowerCase());
    var head = el("h2", null, label + " - " + naira(record.amount_kobo));
    if (isSample) { head.appendChild(el("span", "tag", "Sample")); }
    card.appendChild(head);
    var meta = [];
    if (record.claimed_bank) { meta.push(record.claimed_bank); }
    if (record.checked_at) { meta.push(record.checked_at); }
    if (record.channel) { meta.push(record.channel); }
    if (meta.length) { card.appendChild(el("div", null, meta.join(" | "))); }
    addList(card, "Warning signs", flagSentences(record.red_flags));
    addList(card, "Reasons", record.reasons);
    addList(card, "Extra care", record.risk_notes);
    return card;
  }

  function render() {
    var box = document.getElementById("cards");
    clear(box);
    var shown = [];
    state.records.forEach(function (r) { shown.push({ r: r, s: false }); });
    if (state.showSample) {
      state.sample.forEach(function (r) { shown.push({ r: r, s: true }); });
    }
    shown = shown.filter(function (x) {
      return state.filter === "ALL" || x.r.owner_label === state.filter;
    });
    if (!shown.length) {
      box.appendChild(el("p", "empty", "No checks to show yet."));
      return;
    }
    shown.forEach(function (x) { box.appendChild(buildCard(x.r, x.s)); });
  }

  function load() {
    fetch("/lab/data", { cache: "no-store" })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        state.records = Array.isArray(data.records) ? data.records : [];
        state.sample = Array.isArray(data.sample) ? data.sample : [];
        if (!state.touched) { state.showSample = state.records.length === 0; }
        document.getElementById("sample-toggle").checked = state.showSample;
        render();
      })
      .catch(function () {
        var box = document.getElementById("cards");
        clear(box);
        box.appendChild(el("p", "empty", "Could not load checks."));
      });
  }

  function showResult(data) {
    var box = document.getElementById("result");
    clear(box);
    var label = LABELS.indexOf(data.owner_label) >= 0 ? data.owner_label : "UNVERIFIED";
    var card = el("article", "card " + label.toLowerCase());
    card.appendChild(el("h2", null, label + " - " + naira(data.amount_kobo)));
    card.appendChild(el("pre", null, data.reply || ""));
    box.appendChild(card);
  }

  function showMessage(text) {
    var box = document.getElementById("result");
    clear(box);
    box.appendChild(el("p", "empty", text));
  }

  document.getElementById("sample-toggle").addEventListener("change", function (ev) {
    state.touched = true;
    state.showSample = ev.target.checked;
    render();
  });

  document.getElementById("filter").addEventListener("change", function (ev) {
    state.filter = ev.target.value;
    render();
  });

  document.getElementById("try-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var text = document.getElementById("try-text").value;
    showMessage("Checking...");
    fetch("/lab/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text })
    })
      .then(function (resp) {
        if (resp.status === 429) { showMessage("Too many tries. Wait a minute and try again."); return null; }
        if (resp.status === 413) { showMessage("That text is too long. Keep it under 2000 characters."); return null; }
        if (!resp.ok) { showMessage("Could not check that text."); return null; }
        return resp.json();
      })
      .then(function (data) {
        if (data) { showResult(data); load(); }
      })
      .catch(function () { showMessage("Could not check that text."); });
  });

  load();
})();
"""

_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Lab - Ghost Credit</title>
<style>__CSS__</style>
</head>
<body>
<header>
<h1>The Lab</h1>
<p class="sub">Recent credit alert checks. No message text or phone numbers are kept.</p>
</header>
<main>
<section>
<h2>Try an alert</h2>
<form id="try-form" action="/lab/check" method="post">
<label for="try-text">Paste a sample alert text</label>
<textarea id="try-text" name="text" maxlength="2000"></textarea>
<button type="submit">Check this alert</button>
</form>
<div id="result" aria-live="polite"></div>
</section>
<section>
<h2>Recent checks</h2>
<div class="controls">
<label for="filter">Show</label>
<select id="filter">
<option value="ALL">All</option>
<option value="ALIVE">ALIVE</option>
<option value="GHOST">GHOST</option>
<option value="SUSPICIOUS">SUSPICIOUS</option>
<option value="UNVERIFIED">UNVERIFIED</option>
</select>
<label><input type="checkbox" id="sample-toggle"> Show sample data</label>
</div>
<div id="cards"></div>
</section>
</main>
<script>__JS__</script>
</body>
</html>
"""


def render_page() -> str:
    """Return the whole /lab page as one self-contained HTML string.

    Why: no external file, font or script is used, and no record data is
    written into the HTML. The page loads records from /lab/data and puts
    every value on screen with textContent only.
    """
    flags = {code: FLAG_REASONS[code] for code in FLAG_ORDER if code in FLAG_REASONS}
    flags_json = json.dumps(flags).replace("<", "\\u003c")
    script = _PAGE_JS.replace("__FLAGS__", flags_json)
    return _PAGE_HTML.replace("__CSS__", _PAGE_CSS).replace("__JS__", script)
