"""Choose the verdict for a credit alert and add plain-English risk notes.

``decide`` follows the fixed rules in .kiro/steering/payments-nigeria.md, in
order. Only Paystack can confirm money. A pattern-network match can only turn
UNVERIFIED into SUSPICIOUS. ``risk_notes`` gives extra cautions that never
change the verdict. Nothing here calls the network, a file, a clock or an AI.
"""

from __future__ import annotations

import copy
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ghost_credit.parser import ParsedAlert
from ghost_credit.paystack import (
    CONFIRMED as _PAYSTACK_CONFIRMED,
    NOT_FOUND as _PAYSTACK_NOT_FOUND,
    PaystackResult,
)
from ghost_credit.pattern_network import LookupResult, Verdict

__all__ = [
    "CONFIRMED",
    "NOT_FOUND",
    "SUSPICIOUS",
    "UNVERIFIED",
    "CHECK_REMINDER",
    "MAX_REASON_LENGTH",
    "DEFAULT_LARGE_AMOUNT_KOBO",
    "OWNER_LABELS",
    "COLLECTION_TERMS",
    "decide",
    "risk_notes",
    "Decision",
    "decide_with_notes",
    "Explainer",
    "FakeExplainer",
    "TemplateExplainer",
    "build_reply",
]

CONFIRMED = "CONFIRMED"
NOT_FOUND = "NOT_FOUND"
SUSPICIOUS = "SUSPICIOUS"
UNVERIFIED = "UNVERIFIED"

CHECK_REMINDER = "Check your own bank app before releasing goods."
MAX_REASON_LENGTH = 120
DEFAULT_LARGE_AMOUNT_KOBO = 50000000  # NGN 500,000

OWNER_LABELS = {
    CONFIRMED: "ALIVE",
    NOT_FOUND: "GHOST",
    SUSPICIOUS: "SUSPICIOUS",
    UNVERIFIED: "UNVERIFIED",
}

# Paystack states used inside this module.
_STATE_CONFIRMED = "confirmed"
_STATE_NO_MATCH = "no_match"
_STATE_NO_CHECK = "no_check"

# Lagos is a fixed +01:00 all year (no daylight saving).
_LAGOS = timezone(timedelta(hours=1))

REASON_CONFIRMED = "Paystack found a matching payment."
REASON_NOT_FOUND = "Paystack found no matching payment."
REASON_NETWORK = "The pattern network has seen a similar alert."
REASON_UNVERIFIED = "No Paystack check was possible and no red flags were found."
REASON_FALLBACK = "The check could not be completed."
REASON_UNKNOWN_FLAG = "Something else about this alert looks wrong."

# Everyday-words reason for each red flag code. No code names, no customer talk.
FLAG_REASONS = {
    "SENDER_ID_MISMATCH": "The message came from a phone number, not from a bank.",
    "BALANCE_LINE_MISSING": "The alert has no available balance line, which banks normally include.",
    "AMOUNT_FORMAT_ODD": "The amount is written in a strange way.",
    "DATE_ODD": "The date or time on the alert looks wrong.",
    "PRESSURE_LANGUAGE": "The message pushes you to release goods before you can check.",
    "SCREENSHOT_EDIT_SIGNS": "The screenshot shows signs it may have been edited.",
    "TRANSFER_REQUEST_WORDING": "The message says a transfer was requested, not received.",
}

NOTE_WEEKEND = "Sent late on a Friday or at the weekend, a common time for fake alerts."
NOTE_LARGE = "Large amount. Take extra care before releasing goods."
NOTE_COLLECT = (
    "Someone is coming to collect at once. "
    "Do not release goods until the money shows in your bank app."
)

COLLECTION_TERMS = ("rider", "dispatch", "driver", "pick up now", "pickup now")
_COLLECTION_PATTERNS = tuple(
    re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)") for term in COLLECTION_TERMS
)
_QUOTE_TABLE = str.maketrans(
    {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}
)
_WHITESPACE = re.compile(r"\s+")


def _paystack_state(paystack_result: object) -> str:
    """Map any Paystack input to confirmed, no_match or no_check.

    Anything unreadable counts as no_check, so junk can never confirm money.
    """
    try:
        if not isinstance(paystack_result, PaystackResult):
            return _STATE_NO_CHECK
        status = paystack_result.status
        checked = paystack_result.checked
        if status == _PAYSTACK_CONFIRMED:
            return _STATE_CONFIRMED
        if status == _PAYSTACK_NOT_FOUND and checked is True:
            return _STATE_NO_MATCH
    except Exception:  # noqa: BLE001 - unreadable input means no Paystack check
        return _STATE_NO_CHECK
    return _STATE_NO_CHECK


def _flags_of(parsed: object) -> list:
    """Return a new list of the alert's red flags; None or a non-list gives []."""
    flags = getattr(parsed, "red_flags", None)
    if not isinstance(flags, list):
        return []
    return list(flags)


def _is_network_match(lookup_result: object) -> bool:
    """True only when the network answered and said it matched."""
    available = getattr(lookup_result, "network_available", None)
    matched = getattr(lookup_result, "matched", None)
    return available is True and matched is True


def _cut(text: str) -> str:
    """Cut a reason to its first 120 characters so it stays short on WhatsApp."""
    return text[:MAX_REASON_LENGTH]


def _flag_reason(flag: object) -> str:
    """Return the everyday-words reason for one red flag entry."""
    if isinstance(flag, str):
        return FLAG_REASONS.get(flag, REASON_UNKNOWN_FLAG)
    return REASON_UNKNOWN_FLAG


def _make_verdict(code: str, checked: bool, reasons: list[str]) -> Verdict:
    """Build a rules verdict with every reason cut to the length limit."""
    cut = [_cut(r) for r in reasons if r]
    return Verdict(
        code=code,
        paystack_checked=checked,
        decided_by="rules",
        owner_outcome="unknown",
        reasons=cut or [_cut(REASON_FALLBACK)],
    )


def _fallback_verdict() -> Verdict:
    """The safe answer when something unexpected goes wrong: UNVERIFIED."""
    return Verdict(
        code=UNVERIFIED,
        paystack_checked=False,
        decided_by="rules",
        owner_outcome="unknown",
        reasons=[REASON_FALLBACK],
    )


def decide(
    parsed: ParsedAlert | None,
    paystack_result: PaystackResult | None,
    lookup_result: LookupResult | None,
) -> Verdict:
    """Pick the verdict by the fixed rules, stopping at the first that applies.

    It never raises and never changes its arguments. Only a Paystack
    confirmation gives CONFIRMED; the network can only add suspicion.
    """
    try:
        state = _paystack_state(paystack_result)
        flags = _flags_of(parsed)
        network = _is_network_match(lookup_result)
        if state == _STATE_CONFIRMED:
            return _make_verdict(CONFIRMED, True, [REASON_CONFIRMED])
        if state == _STATE_NO_MATCH:
            return _make_verdict(NOT_FOUND, True, [REASON_NOT_FOUND])
        if flags:
            return _make_verdict(SUSPICIOUS, False, [_flag_reason(f) for f in flags])
        if network:
            return _make_verdict(SUSPICIOUS, False, [REASON_NETWORK])
        return _make_verdict(UNVERIFIED, False, [REASON_UNVERIFIED])
    except Exception:  # noqa: BLE001 - the owner must always get an answer
        return _fallback_verdict()


# --- Risk notes -----------------------------------------------------------


def _normalise_text(text: str) -> str:
    """Straighten curly quotes, lower-case, and squeeze whitespace to one space."""
    return _WHITESPACE.sub(" ", text.translate(_QUOTE_TABLE).lower())


def _to_lagos(moment: datetime) -> datetime:
    """Return the time as Lagos time. Naive means Lagos already."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        return moment.replace(tzinfo=_LAGOS)
    return moment.astimezone(_LAGOS)


def _is_late_or_weekend(moment: object) -> bool:
    """True for Friday from 14:00, Saturday or Sunday, in Lagos time."""
    if not isinstance(moment, datetime):
        return False
    lagos = _to_lagos(moment)
    weekday = lagos.weekday()
    return (weekday == 4 and lagos.hour >= 14) or weekday in (5, 6)


def _is_int(value: object) -> bool:
    """True for a real int. A bool is refused because True == 1 in Python."""
    return isinstance(value, int) and not isinstance(value, bool)


def _threshold(value: object) -> int:
    """Return the large-amount limit in kobo, or the default if it is not an int."""
    return value if _is_int(value) else DEFAULT_LARGE_AMOUNT_KOBO  # type: ignore[return-value]


def _mentions_collection(alert_text: object) -> bool:
    """True when the alert text names a rider, driver, dispatch or 'pick up now'."""
    if not isinstance(alert_text, str):
        return False
    text = _normalise_text(alert_text)
    return any(p.search(text) for p in _COLLECTION_PATTERNS)


def risk_notes(
    parsed: ParsedAlert | None,
    *,
    alert_text: str | None = None,
    large_amount_kobo: int = DEFAULT_LARGE_AMOUNT_KOBO,
) -> list[str]:
    """Return plain-English cautions in a fixed order, each at most once.

    Notes are advice only. They never change a verdict. Any error gives [].
    """
    try:
        notes: list[str] = []
        if _is_late_or_weekend(getattr(parsed, "alert_time", None)):
            notes.append(NOTE_WEEKEND)
        amount = getattr(parsed, "amount_kobo", None)
        if _is_int(amount) and amount >= _threshold(large_amount_kobo):
            notes.append(NOTE_LARGE)
        if _mentions_collection(alert_text):
            notes.append(NOTE_COLLECT)
        return notes
    except Exception:  # noqa: BLE001 - a failed note must never block the reply
        return []


# --- Decision with notes --------------------------------------------------


@dataclass(frozen=True)
class Decision:
    """A verdict together with its risk notes. Notes never change the verdict."""

    verdict: Verdict
    risk_notes: list


def decide_with_notes(
    parsed: ParsedAlert | None,
    paystack_result: PaystackResult | None,
    lookup_result: LookupResult | None,
    *,
    alert_text: str | None = None,
    large_amount_kobo: int = DEFAULT_LARGE_AMOUNT_KOBO,
) -> Decision:
    """Run ``decide`` and ``risk_notes`` separately and return both together."""
    verdict = decide(parsed, paystack_result, lookup_result)
    notes = risk_notes(
        parsed, alert_text=alert_text, large_amount_kobo=large_amount_kobo
    )
    return Decision(verdict=verdict, risk_notes=notes)


# --- Explainers -----------------------------------------------------------


class Explainer(ABC):
    """Writes the words of a reply. It can never change the verdict."""

    @abstractmethod
    def explain(
        self, verdict: Verdict, parsed: ParsedAlert | None, risk_notes: list[str]
    ) -> str:
        """Return the explanation text for this verdict."""


class FakeExplainer(Explainer):
    """A test Explainer: same input gives the same text, no outside calls."""

    def explain(
        self, verdict: Verdict, parsed: ParsedAlert | None, risk_notes: list[str]
    ) -> str:
        """Return a fixed string made from the code, the reasons and the notes."""
        lines = [f"[{verdict.code}]"]
        lines.extend(str(r) for r in verdict.reasons)
        lines.extend(str(n) for n in risk_notes)
        return "\n".join(lines)


_HEADLINES = {
    CONFIRMED: (
        "ALIVE. You can release the goods. "
        "Paystack has a matching payment for this alert."
    ),
    NOT_FOUND: (
        "GHOST. Hold the goods. Paystack has no matching payment for this alert."
    ),
    SUSPICIOUS: "SUSPICIOUS. Hold the goods. This alert has warning signs.",
    UNVERIFIED: (
        "UNVERIFIED. Check first before you release anything. "
        "Nothing here proves this alert either way."
    ),
}
_MAX_TEMPLATE_REASONS = 3


class TemplateExplainer(Explainer):
    """Builds the reply from fixed text only. No AI and no network."""

    def explain(
        self, verdict: Verdict, parsed: ParsedAlert | None, risk_notes: list[str]
    ) -> str:
        """Write headline, up to 3 reasons, risk notes, then the reminder."""
        code = getattr(verdict, "code", None)
        headline = _HEADLINES.get(code, _HEADLINES[UNVERIFIED])
        reasons = [r for r in (getattr(verdict, "reasons", None) or []) if isinstance(r, str)]
        items = reasons[:_MAX_TEMPLATE_REASONS] + [
            n for n in risk_notes if isinstance(n, str)
        ]
        lines = [headline]
        if items:
            lines.append("")
            lines.append("Why:")
            lines.extend(f"- {item}" for item in items)
        if code != CONFIRMED:
            lines.append("")
            lines.append(CHECK_REMINDER)
        return "\n".join(lines)


# --- Reply builder --------------------------------------------------------


def _fallback_text(verdict: object, notes: list[str]) -> str:
    """Reasons joined with one space, then each note on its own line."""
    reasons = getattr(verdict, "reasons", None)
    good = [r for r in reasons if isinstance(r, str)] if isinstance(reasons, list) else []
    parts = []
    if good:
        parts.append(" ".join(good))
    parts.extend(notes)
    return "\n".join(parts)


def build_reply(
    verdict: Verdict,
    parsed: ParsedAlert | None,
    explainer: Explainer,
    risk_notes: list[str] | None = None,
) -> str:
    """Ask the Explainer for text, fall back to the reasons, and add the reminder.

    Never raises. The reminder is added for every code except CONFIRMED, once.
    """
    try:
        code = getattr(verdict, "code", None)
    except Exception:  # noqa: BLE001
        code = None
    try:
        notes = [n for n in (risk_notes or []) if isinstance(n, str)]
    except Exception:  # noqa: BLE001
        notes = []
    try:
        text = explainer.explain(copy.deepcopy(verdict), parsed, list(notes))
    except Exception:  # noqa: BLE001 - a bad Explainer must not stop the reply
        text = None
    if not isinstance(text, str) or not text.strip():
        try:
            text = _fallback_text(verdict, notes)
        except Exception:  # noqa: BLE001
            text = "\n".join(notes)
    if code == CONFIRMED:
        return text
    text = text.rstrip()
    if text.endswith(CHECK_REMINDER):
        return text
    return f"{text}\n{CHECK_REMINDER}" if text else CHECK_REMINDER
