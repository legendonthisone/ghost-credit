"""Pattern network plug socket (contract v1.0, docs/pattern-network-contract.md).

This repo ships only the off version: contract dataclasses, an abstract
PatternNetwork, NoopPatternNetwork, and helpers that clean and hash payer
details. There is no network code here. Standard library only.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional, Sequence

__all__ = [
    "Verdict",
    "Signals",
    "Match",
    "LookupResult",
    "ReportReceipt",
    "PatternNetwork",
    "NoopPatternNetwork",
    "normalise_name",
    "normalise_phone",
    "normalise_account",
    "hash_value",
    "is_hook_on",
    "get_hmac_key",
    "get_merchant_ref",
    "get_network",
    "build_signals",
    "safe_lookup",
    "safe_report",
]

SCHEMA_VERSION = "1.0"
VERDICT_CODES = ("CONFIRMED", "NOT_FOUND", "SUSPICIOUS", "UNVERIFIED")
OWNER_OUTCOMES = ("unknown", "fake", "real")
RECEIPT_STATUSES = ("disabled", "queued", "rejected")


def _known(cls: type, data: Dict[str, Any]) -> Dict[str, Any]:
    """Pick only the contract fields from a dict, so unknown keys are ignored."""
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in names}


@dataclass
class Signals:
    """What Ghost Credit knows about one check (contract table `signals`)."""

    check_id: str
    checked_at: str
    channel: str
    amount_kobo: int
    schema_version: str = SCHEMA_VERSION
    currency: str = "NGN"
    claimed_bank: Optional[str] = None
    sender_id: Optional[str] = None
    claimed_reference: Optional[str] = None
    payer_name_hash: Optional[str] = None
    payer_account_hash: Optional[str] = None
    payer_phone_hash: Optional[str] = None
    screenshot_phash: Optional[str] = None
    red_flags: List[str] = field(default_factory=list)
    merchant_ref: Optional[str] = None
    merchant_category: str = "unknown"

    def __post_init__(self) -> None:
        """Reject an amount that is not a whole number of kobo."""
        if isinstance(self.amount_kobo, bool) or not isinstance(self.amount_kobo, int):
            raise ValueError("amount_kobo must be an integer (kobo)")

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary using the contract field names."""
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["red_flags"] = list(self.red_flags)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signals":
        """Build Signals from a dictionary, ignoring unknown fields."""
        return cls(**_known(cls, data))


@dataclass
class Verdict:
    """The rules' verdict for one check (contract table `verdict`)."""

    code: str
    paystack_checked: bool
    decided_by: str = "rules"
    owner_outcome: str = "unknown"
    reasons: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Reject codes and owner outcomes the contract does not allow."""
        if self.code not in VERDICT_CODES:
            raise ValueError("code must be one of " + ", ".join(VERDICT_CODES))
        if self.owner_outcome not in OWNER_OUTCOMES:
            raise ValueError("owner_outcome must be one of " + ", ".join(OWNER_OUTCOMES))

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary using the contract field names."""
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["reasons"] = list(self.reasons)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Verdict":
        """Build a Verdict from a dictionary, ignoring unknown fields."""
        return cls(**_known(cls, data))


@dataclass
class Match:
    """One pattern the network says it has seen before."""

    pattern_id: str
    matched_on: List[str] = field(default_factory=list)
    first_seen: Optional[str] = None
    times_seen: int = 0
    shops_seen: int = 0
    last_verdict: Optional[str] = None
    confidence: float = 0.0
    summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary using the contract field names."""
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["matched_on"] = list(self.matched_on)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Match":
        """Build a Match from a dictionary, ignoring unknown fields."""
        return cls(**_known(cls, data))


@dataclass
class LookupResult:
    """The network's answer to lookup_patterns."""

    network_available: bool
    matched: bool
    matches: List[Match] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    trace_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary, with each Match as a dictionary."""
        return {
            "schema_version": self.schema_version,
            "network_available": self.network_available,
            "matched": self.matched,
            "matches": [m.to_dict() for m in self.matches],
            "trace_url": self.trace_url,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LookupResult":
        """Build a LookupResult from a dictionary, ignoring unknown fields."""
        kwargs = _known(cls, data)
        kwargs["matches"] = [
            m if isinstance(m, Match) else Match.from_dict(m)
            for m in kwargs.get("matches", [])
        ]
        return cls(**kwargs)


@dataclass
class ReportReceipt:
    """The network's answer to report_pattern."""

    accepted: bool
    status: str
    pattern_id: Optional[str] = None
    schema_version: str = SCHEMA_VERSION
    trace_url: Optional[str] = None

    def __post_init__(self) -> None:
        """Reject a status the contract does not allow."""
        if self.status not in RECEIPT_STATUSES:
            raise ValueError("status must be one of " + ", ".join(RECEIPT_STATUSES))

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary using the contract field names."""
        return {
            "schema_version": self.schema_version,
            "accepted": self.accepted,
            "status": self.status,
            "pattern_id": self.pattern_id,
            "trace_url": self.trace_url,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportReceipt":
        """Build a ReportReceipt from a dictionary, ignoring unknown fields."""
        return cls(**_known(cls, data))


class PatternNetwork(ABC):
    """The one plug socket. Anything plugged in must answer these two calls."""

    @abstractmethod
    def lookup_patterns(self, signals: Signals) -> LookupResult:
        """Ask the network whether it has seen this pattern before."""

    @abstractmethod
    def report_pattern(self, verdict: Verdict, signals: Signals) -> ReportReceipt:
        """Tell the network about a verdict that was not CONFIRMED."""


class NoopPatternNetwork(PatternNetwork):
    """The only network in this repo: always 'not available', sends nothing."""

    def lookup_patterns(self, signals: Signals) -> LookupResult:
        """Answer 'network not available' without looking at the signals."""
        return LookupResult(network_available=False, matched=False, matches=[], trace_url=None)

    def report_pattern(self, verdict: Verdict, signals: Signals) -> ReportReceipt:
        """Answer 'disabled' and keep the report nowhere."""
        return ReportReceipt(accepted=False, status="disabled", pattern_id=None, trace_url=None)


# --- Normaliser -----------------------------------------------------------

_PHONE_FILLER = re.compile(r"[ \-()]")
_PHONE_FORM = re.compile(r"(?:\+234|234|0)([0-9]{10})", re.ASCII)
_ACCOUNT_FILLER = re.compile(r"[ \-]")
_ACCOUNT_FORM = re.compile(r"[0-9]{10}", re.ASCII)


def normalise_name(raw: Optional[str]) -> Optional[str]:
    """Clean a payer name (uppercase, no punctuation, single spaces) so equal names hash equal."""
    if raw is None:
        return None
    kept = "".join(ch for ch in raw.upper() if ch.isalnum() or ch.isspace())
    result = " ".join(kept.split())
    return result or None


def normalise_phone(raw: Optional[str]) -> Optional[str]:
    """Turn a Nigerian phone into +234 plus 10 digits, or None if it is not clearly one."""
    if raw is None:
        return None
    match = _PHONE_FORM.fullmatch(_PHONE_FILLER.sub("", raw))
    return "+234" + match.group(1) if match else None


def normalise_account(raw: Optional[str]) -> Optional[str]:
    """Return a 10-digit NUBAN account number, or None if it is masked or malformed."""
    if raw is None:
        return None
    cleaned = _ACCOUNT_FILLER.sub("", raw)
    return cleaned if _ACCOUNT_FORM.fullmatch(cleaned) else None


# --- Hasher ---------------------------------------------------------------


def hash_value(value: Optional[str], key: Optional[str]) -> Optional[str]:
    """Return 'hmac:' plus the HMAC-SHA256 hex of a value, or None if value or key is missing."""
    if value is None or not key:
        return None
    digest = hmac.new(key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256)
    return "hmac:" + digest.hexdigest()


# --- Hook_Config ----------------------------------------------------------

_ENV_SWITCH = "PATTERN_NETWORK"
_ENV_KEY = "PATTERN_NETWORK_HMAC_KEY"
_ENV_MERCHANT_REF = "PATTERN_NETWORK_MERCHANT_REF"
LOOKUP_TIMEOUT_SECONDS = 1.5

_log = logging.getLogger(__name__)


def is_hook_on() -> bool:
    """Say whether the hook is on: only when PATTERN_NETWORK is 'on' (any case, trimmed)."""
    return os.environ.get(_ENV_SWITCH, "").strip().lower() == "on"


def get_hmac_key() -> Optional[str]:
    """Return the network-wide HMAC key, or None if the hook is off or no key is set."""
    if not is_hook_on():
        return None
    return os.environ.get(_ENV_KEY) or None


def get_merchant_ref() -> Optional[str]:
    """Return this shop's opaque merchant_ref, or None if the hook is off or none is set."""
    if not is_hook_on():
        return None
    return os.environ.get(_ENV_MERCHANT_REF) or None


def get_network() -> PatternNetwork:
    """Return the network to use. In this repo that is always the no-op one."""
    return NoopPatternNetwork()


# --- Signals privacy builder ----------------------------------------------


def build_signals(
    *,
    check_id: str,
    checked_at: str,
    channel: str,
    amount_kobo: int,
    currency: str = "NGN",
    claimed_bank: Optional[str] = None,
    sender_id: Optional[str] = None,
    claimed_reference: Optional[str] = None,
    screenshot_phash: Optional[str] = None,
    red_flags: Sequence[str] = (),
    merchant_category: str = "other",
    payer_name: Optional[str] = None,
    payer_account: Optional[str] = None,
    payer_phone: Optional[str] = None,
) -> Signals:
    """Build Signals, turning raw payer details into keyed hashes so no raw value is kept.

    With the hook off (or no key) the payer hashes are None. The raw payer
    arguments are never stored in the result.
    """
    key = get_hmac_key()
    return Signals(
        check_id=check_id,
        checked_at=checked_at,
        channel=channel,
        amount_kobo=amount_kobo,
        currency=currency,
        claimed_bank=claimed_bank,
        sender_id=sender_id,
        claimed_reference=claimed_reference,
        payer_name_hash=hash_value(normalise_name(payer_name), key),
        payer_account_hash=hash_value(normalise_account(payer_account), key),
        payer_phone_hash=hash_value(normalise_phone(payer_phone), key),
        screenshot_phash=screenshot_phash,
        red_flags=list(red_flags),
        merchant_ref=get_merchant_ref(),
        merchant_category=merchant_category,
    )


# --- Network_Caller -------------------------------------------------------


def _unavailable() -> LookupResult:
    """Return the safe 'network not available' answer."""
    return LookupResult(network_available=False, matched=False, matches=[], trace_url=None)


def safe_lookup(network: PatternNetwork, signals: Signals) -> LookupResult:
    """Ask the network, waiting at most 1.5 seconds; on any trouble say 'not available'.

    The answer is advice only. It is never turned into a verdict here.
    """
    box: Dict[str, Any] = {}

    def work() -> None:
        try:
            box["result"] = network.lookup_patterns(signals)
        except Exception as exc:  # noqa: BLE001 - any failure means 'not available'
            box["error"] = type(exc).__name__

    worker = threading.Thread(target=work, name="pattern-lookup", daemon=True)
    worker.start()
    worker.join(LOOKUP_TIMEOUT_SECONDS)
    if worker.is_alive():
        _log.warning("pattern network lookup timed out")
        return _unavailable()
    if "error" in box:
        _log.warning("pattern network lookup failed: %s", box["error"])
        return _unavailable()
    result = box.get("result")
    if not isinstance(result, LookupResult):
        _log.warning("pattern network lookup returned an unexpected answer")
        return _unavailable()
    return result


def safe_report(
    network: PatternNetwork, verdict: Verdict, signals: Signals
) -> Optional[threading.Thread]:
    """Report a non-CONFIRMED verdict on a background thread and return at once.

    Errors are dropped and logged by type only. Returns the thread (so tests can
    wait for it), or None when nothing is reported.
    """
    if verdict.code == "CONFIRMED":
        return None

    def work() -> None:
        try:
            network.report_pattern(verdict, signals)
        except Exception as exc:  # noqa: BLE001 - a failed report must never reach the owner
            _log.warning("pattern network report failed: %s", type(exc).__name__)

    worker = threading.Thread(target=work, name="pattern-report", daemon=True)
    worker.start()
    return worker
