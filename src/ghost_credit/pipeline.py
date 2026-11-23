"""Check pipeline: run one whole credit-alert check from start to finish.

``run_check`` reads the alert (text, screenshot or both), asks Paystack, asks
the pattern network, lets the verdict rules decide, writes the reply and
reports the pattern. This module only wires existing parts together. It holds
no verdict rules and makes no AI call. Every dependency is passed in, so tests
use fakes. Nothing here writes to disk or keeps the image bytes.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from ghost_credit.parser import RED_FLAG_CODES, ParsedAlert, parse_sms_alert
from ghost_credit.pattern_network import (
    LookupResult,
    NoopPatternNetwork,
    Signals,
    Verdict,
    build_signals,
    safe_lookup,
    safe_report,
)
from ghost_credit.paystack import UNAVAILABLE, PaystackResult, verify
from ghost_credit.screenshot import FakeScreenshotReader
from ghost_credit.verdict import (
    CHECK_REMINDER,
    TemplateExplainer,
    build_reply,
    decide_with_notes,
)

__all__ = ["CheckResult", "run_check", "merge_alerts", "make_paystack_verify"]

FALLBACK_REASON = "The check could not be completed."
UNAVAILABLE_REASON = "could not check Paystack"
DEFAULT_CATEGORY = "other"
# Lagos is a fixed +01:00 all year (no daylight saving).
LAGOS = timezone(timedelta(hours=1))

# Known red flag codes, in the parser's order.
FLAG_ORDER = tuple(RED_FLAG_CODES)

_log = logging.getLogger("ghost_credit.pipeline")

PaystackCallable = Callable[[ParsedAlert, datetime], PaystackResult]


@dataclass(frozen=True)
class CheckResult:
    """Everything one check produced, ready for the app to show."""

    check_id: str
    parsed: ParsedAlert
    paystack_result: PaystackResult
    verdict: Verdict
    reply: str
    risk_notes: list[str]


# The "could not check Paystack" answer, used when the Paystack step fails.
_UNAVAILABLE = PaystackResult(UNAVAILABLE, False, None, None, None, UNAVAILABLE_REASON)


def _log_failure(step: str, exc: BaseException) -> None:
    """Log which step failed and the error type only, never any alert data."""
    _log.warning("step %s failed: %s", step, type(exc).__name__)


def _safe_fallback(check_id: str, parsed: ParsedAlert) -> CheckResult:
    """Build the cautious UNVERIFIED result from fixed values only.

    Why: when anything breaks, the owner must still get a safe answer, and it
    must never say money arrived. Each call makes new objects.
    """
    verdict = Verdict(
        code="UNVERIFIED",
        paystack_checked=False,
        decided_by="rules",
        owner_outcome="unknown",
        reasons=[FALLBACK_REASON],
    )
    return CheckResult(
        check_id=check_id,
        parsed=parsed,
        paystack_result=_UNAVAILABLE,
        verdict=verdict,
        reply=FALLBACK_REASON + " " + CHECK_REMINDER,
        risk_notes=[],
    )


def make_paystack_verify(http: Callable | None = None) -> PaystackCallable:
    """Return a Paystack callable that reads the secret key when it is called.

    Why: the key stays inside this closure, so it can never reach a result,
    a log line or an error message. No key means no network call.
    """

    def call(parsed: ParsedAlert, now: datetime) -> PaystackResult:
        """Check one alert against Paystack using the key from the environment."""
        key = os.environ.get("PAYSTACK_SECRET_KEY") or None
        return verify(parsed, key, now, http=http)

    return call


def _lagos_iso(now: datetime) -> str:
    """Write ``now`` as ISO 8601 text at +01:00; a naive time counts as Lagos."""
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")
    if now.tzinfo is None or now.utcoffset() is None:
        moment = now.replace(tzinfo=LAGOS)
    else:
        moment = now.astimezone(LAGOS)
    return moment.isoformat(timespec="seconds")


def _clean_category(value: object) -> str:
    """Return the trimmed merchant category, or "other" when it is blank."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return DEFAULT_CATEGORY


# --- Sources and merge ----------------------------------------------------


def _text_usable(text: object) -> bool:
    """True when the text is a string with at least one visible character."""
    return isinstance(text, str) and bool(text.strip())


def _image_usable(image_bytes: object) -> bool:
    """True when the image is non-empty bytes."""
    return isinstance(image_bytes, bytes) and len(image_bytes) > 0


def _read_text(text: object, sender_id: object) -> ParsedAlert | None:
    """Parse the SMS text once, or return None when there is no usable text."""
    if not _text_usable(text):
        return None
    return parse_sms_alert(text, sender_id if isinstance(sender_id, str) else None)


def _read_image(reader: object, image_bytes: object) -> ParsedAlert | None:
    """Read the screenshot once, or return None when there is no usable image.

    A reader that fails or returns the wrong type gives an empty alert, so the
    check carries on. The bytes are not kept anywhere.
    """
    if not _image_usable(image_bytes):
        return None
    try:
        result = reader.read(image_bytes)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - an unreadable screenshot is not fatal
        _log_failure("read_image", exc)
        return ParsedAlert()
    if not isinstance(result, ParsedAlert):
        _log_failure("read_image", TypeError())
        return ParsedAlert()
    return result


def _merge_flags(first: object, second: object) -> list[str]:
    """Join two flag lists: each code once, known codes first, then others."""
    seen: list[str] = []
    for source in (first, second):
        if not isinstance(source, list):
            continue
        for code in source:
            if isinstance(code, str) and code not in seen:
                seen.append(code)
    known = [code for code in FLAG_ORDER if code in seen]
    others = [code for code in seen if code not in FLAG_ORDER]
    return known + others


def merge_alerts(
    text_alert: ParsedAlert | None,
    image_alert: ParsedAlert | None,
    sender_id: object,
) -> ParsedAlert:
    """Combine the text and screenshot alerts; text values win, gaps are filled.

    Why: each source may show details the other does not. The inputs are left
    unchanged and a new alert is returned.
    """
    values: dict[str, object] = {}
    for item in dataclasses.fields(ParsedAlert):
        name = item.name
        if name in ("red_flags", "sender_id", "screenshot_phash"):
            continue
        value = getattr(text_alert, name, None) if text_alert is not None else None
        if value is None and image_alert is not None:
            value = getattr(image_alert, name, None)
        values[name] = value
    values["screenshot_phash"] = (
        getattr(image_alert, "screenshot_phash", None) if image_alert is not None else None
    )
    values["sender_id"] = sender_id if isinstance(sender_id, str) else None
    values["red_flags"] = _merge_flags(
        getattr(text_alert, "red_flags", None), getattr(image_alert, "red_flags", None)
    )
    return ParsedAlert(**values)  # type: ignore[arg-type]


# --- Paystack and network steps -------------------------------------------


def _check_paystack(
    paystack_verify: Callable, parsed: ParsedAlert, now: object
) -> PaystackResult:
    """Call the Paystack callable once; any failure gives the unavailable result."""
    try:
        result = paystack_verify(parsed, now)
    except Exception as exc:  # noqa: BLE001 - a failed check must not stop the reply
        _log_failure("paystack", exc)
        return _UNAVAILABLE
    if not isinstance(result, PaystackResult):
        _log_failure("paystack", TypeError())
        return _UNAVAILABLE
    return result


def _empty_lookup() -> LookupResult:
    """Return a fresh 'network not available' answer."""
    return LookupResult(network_available=False, matched=False, matches=[])


def _build_signals(
    check_id: str,
    merged: ParsedAlert,
    text: object,
    image_bytes: object,
    merchant_category: object,
    now: object,
) -> Signals | None:
    """Build the network Signals, or None when there is no whole-kobo amount.

    No payer name, phone or account is passed, so the payer hashes stay empty.
    """
    amount = merged.amount_kobo
    if isinstance(amount, bool) or not isinstance(amount, int):
        return None
    try:
        channel = "sms" if _text_usable(text) else "screenshot"
        return build_signals(
            check_id=check_id,
            checked_at=_lagos_iso(now),  # type: ignore[arg-type]
            channel=channel,
            amount_kobo=amount,
            currency="NGN",
            claimed_bank=merged.claimed_bank,
            sender_id=merged.sender_id,
            claimed_reference=merged.claimed_reference,
            screenshot_phash=merged.screenshot_phash,
            red_flags=list(merged.red_flags),
            merchant_category=_clean_category(merchant_category),
        )
    except Exception as exc:  # noqa: BLE001 - no Signals means no network traffic
        _log_failure("build_signals", exc)
        return None


def _report(network: object, verdict: Verdict, signals: Signals) -> None:
    """Report to the network in the background and drop any error."""
    try:
        safe_report(network, verdict, signals)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 - a report must never change the result
        _log_failure("report", exc)


# --- Entry point ----------------------------------------------------------


def run_check(
    text: object,
    sender_id: object,
    image_bytes: object,
    merchant_category: object,
    now: object,
    *,
    reader: object = None,
    paystack_verify: Callable | None = None,
    network: object = None,
    explainer: object = None,
) -> CheckResult:
    """Run one whole check and return a CheckResult. It never raises.

    Steps: read and merge, Paystack, network lookup, decide, reply, report.
    The verdict comes only from the verdict engine. Any unexpected failure
    gives the safe UNVERIFIED fallback.
    """
    check_id = str(uuid.uuid4())
    merged: ParsedAlert | None = None
    try:
        reader = FakeScreenshotReader() if reader is None else reader
        paystack_verify = make_paystack_verify() if paystack_verify is None else paystack_verify
        network = NoopPatternNetwork() if network is None else network
        explainer = TemplateExplainer() if explainer is None else explainer

        text_alert = _read_text(text, sender_id)
        image_alert = _read_image(reader, image_bytes)
        if text_alert is None and image_alert is None:
            return _safe_fallback(check_id, ParsedAlert())
        merged = merge_alerts(text_alert, image_alert, sender_id)

        paystack_result = _check_paystack(paystack_verify, merged, now)
        signals = _build_signals(
            check_id, merged, text, image_bytes, merchant_category, now
        )
        lookup = safe_lookup(network, signals) if signals is not None else _empty_lookup()  # type: ignore[arg-type]

        decision = decide_with_notes(
            merged,
            paystack_result,
            lookup,
            alert_text=text if isinstance(text, str) else None,
        )
        reply = build_reply(decision.verdict, merged, explainer, decision.risk_notes)  # type: ignore[arg-type]
        notes = [n for n in (decision.risk_notes or []) if isinstance(n, str)]
        result = CheckResult(
            check_id=check_id,
            parsed=merged,
            paystack_result=paystack_result,
            verdict=decision.verdict,
            reply=reply,
            risk_notes=notes,
        )
    except Exception as exc:  # noqa: BLE001 - the owner must always get an answer
        _log_failure("run_check", exc)
        return _safe_fallback(check_id, merged if merged is not None else ParsedAlert())

    if signals is not None and result.verdict.code != "CONFIRMED":
        _report(network, result.verdict, signals)
    return result
