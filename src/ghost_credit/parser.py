"""Pure parser for Nigerian bank credit alert SMS text.

``parse_sms_alert`` reads an alert's text and its sender header and returns a
``ParsedAlert``. It makes no AI, network or file calls and keeps no state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

MAX_TEXT_LENGTH = 10_000

RED_FLAG_CODES = (
    "SENDER_ID_MISMATCH",
    "BALANCE_LINE_MISSING",
    "AMOUNT_FORMAT_ODD",
    "DATE_ODD",
    "PRESSURE_LANGUAGE",
    "SCREENSHOT_EDIT_SIGNS",
    "TRANSFER_REQUEST_WORDING",
)

# Lower-case phrases that urge the shop to release goods at once. Edit here.
PRESSURE_PHRASES = (
    "release now",
    "before the owner",
    "send the goods now",
    "i am in a hurry",
    "don't wait",
    "no time",
)

# Lower-case phrases that say a transfer was requested, not received. Edit here.
TRANSFER_REQUEST_PHRASES = (
    "transfer request successful",
    "transfer request has been",
)
_REQUEST_WORDS = "request successful"
_TRANSFER_WORD = "transfer"
_NEAR_LIMIT = 40  # most characters allowed between the two words

# (canonical name, aliases). Aliases are lower case and matched on word boundaries.
KNOWN_BANKS = (
    ("Access Bank", ("access bank", "accessbank")),
    ("GTBank", ("gtbank", "gtb", "guaranty trust")),
    ("Zenith Bank", ("zenith bank", "zenithbank", "zenith")),
    ("First Bank", ("first bank", "firstbank", "fbn")),
    ("UBA", ("uba", "united bank for africa")),
    ("Fidelity Bank", ("fidelity bank", "fidelity")),
    ("FCMB", ("fcmb",)),
    ("Stanbic IBTC", ("stanbic ibtc", "stanbic")),
    ("Sterling Bank", ("sterling bank", "sterling")),
    ("Union Bank", ("union bank", "unionbank")),
    ("Wema Bank", ("wema bank", "wema", "alat")),
    ("Ecobank", ("ecobank",)),
    ("Polaris Bank", ("polaris bank", "polaris")),
    ("Keystone Bank", ("keystone bank", "keystone")),
    ("Providus Bank", ("providus bank", "providus")),
    ("OPay", ("opay",)),
    ("Moniepoint", ("moniepoint",)),
    ("Kuda", ("kuda",)),
    ("PalmPay", ("palmpay",)),
)


@dataclass(frozen=True)
class ParsedAlert:
    """Structured result of parsing one credit alert SMS.

    A field with no value in the input is None. ``red_flags`` is a list of
    unique codes from ``RED_FLAG_CODES``, in that tuple's order.
    ``screenshot_phash`` is set only by the screenshot reader (``phash:`` plus
    16 hex characters). SMS parsing always leaves it None.
    """

    amount_kobo: int | None = None
    currency: str | None = None
    claimed_bank: str | None = None
    sender_id: str | None = None
    account_masked: str | None = None
    narration: str | None = None
    alert_time: datetime | None = None  # naive
    available_balance_kobo: int | None = None
    claimed_reference: str | None = None
    red_flags: list[str] = field(default_factory=list)
    screenshot_phash: str | None = None


Span = tuple[int, int]

_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"
_BALANCE_RE = re.compile(
    r"(?<![A-Za-z])"
    r"(?:available\s+balance|current\s+balance|avail\.?\s*bal\.?|bal\.?)"
    r"(?![A-Za-z])"
    r"\s*[:\-]?\s*"
    r"(?:(?:NGN|\u20a6|N)\s?)?"
    r"(?P<num>" + _NUMBER + r")"
    r"(?!\d)(?![.,]\d)",
    re.IGNORECASE,
)


def _digits_to_kobo(number: str) -> int:
    """Convert digits like ``1,234.5`` to kobo using integer arithmetic only."""
    whole, _, frac = number.replace(",", "").partition(".")
    return int(whole) * 100 + int(frac.ljust(2, "0") or "0")


def _balance_matches(text: str) -> list[tuple[Span, int]]:
    """Return (span, kobo) for each Balance_Line, in text order."""
    return [(m.span(), _digits_to_kobo(m.group("num"))) for m in _BALANCE_RE.finditer(text)]


def _find_balance_lines(text: str) -> list[Span]:
    """Return the span of each Balance_Line (label, separator, marker and figure).

    A balance label with no figure after it yields no span.
    """
    return [span for span, _ in _balance_matches(text)]


_STRICT_NUMBER_RE = re.compile(r"(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.(?P<frac>\d+))?")

# Loose capture: digits, commas and full stops. Validated strictly afterwards.
_MARKER_AMOUNT_RE = re.compile(
    r"(?<![A-Za-z])(?:NGN|\u20a6|N)\s?(?P<tok>\d[\d.,]*)(?P<k>[kK](?![A-Za-z]))?",
)
_CR_AMOUNT_RE = re.compile(
    r"(?<![\d.,])(?P<tok>\d[\d.,]*)\s?CR\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _AmountCandidate:
    span: Span
    kobo: int | None
    has_marker: bool
    status: str  # "ok", "odd_format" or "too_many_decimals"


def _parse_amount_token(number: str, k_suffix: bool = False) -> int | None:
    """Convert a written number (``50,000.00``, ``1.5`` with ``k``) to kobo.

    Uses integer arithmetic only. Returns None unless ``number`` is a number
    with correct comma groups and at most 2 decimal digits.
    """
    m = _STRICT_NUMBER_RE.fullmatch(number)
    if m is None or len(m.group("frac") or "") > 2:
        return None
    kobo = _digits_to_kobo(number)
    return kobo * 1000 if k_suffix else kobo


def _classify_amount(token: str, k_suffix: bool) -> tuple[int | None, str]:
    """Return (kobo, status) for a loose amount token."""
    m = _STRICT_NUMBER_RE.fullmatch(token)
    if m is None:
        return None, "odd_format"
    if len(m.group("frac") or "") > 2:
        return None, "too_many_decimals"
    return _parse_amount_token(token, k_suffix), "ok"


def _overlaps(span: Span, spans: Iterable[Span]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in spans)


def _find_amounts(text: str, masked_spans: Iterable[Span]) -> list[_AmountCandidate]:
    """Scan for marker-form and ``CR``-form amounts outside ``masked_spans``.

    Candidates are returned in text order. A trailing ``.`` or ``,`` after the
    digits is sentence punctuation and is not part of the number.
    """
    masked = list(masked_spans)
    candidates: list[_AmountCandidate] = []
    for m in _MARKER_AMOUNT_RE.finditer(text):
        if _overlaps(m.span(), masked):
            continue
        token = m.group("tok").rstrip(".,")
        if not token:
            continue
        kobo, status = _classify_amount(token, m.group("k") is not None)
        candidates.append(_AmountCandidate(m.span(), kobo, True, status))
    marker_spans = [c.span for c in candidates]
    for m in _CR_AMOUNT_RE.finditer(text):
        if _overlaps(m.span(), masked) or _overlaps(m.span(), marker_spans):
            continue
        token = m.group("tok").rstrip(".,")
        if not token:
            continue
        kobo, status = _classify_amount(token, False)
        candidates.append(_AmountCandidate(m.span(), kobo, False, status))
    candidates.sort(key=lambda c: c.span[0])
    return candidates


def _extract_amount(
    text: str, balance_spans: Iterable[Span]
) -> tuple[int | None, str | None, bool]:
    """Return (amount_kobo, currency, any_odd).

    The first candidate outside a Balance_Line decides ``amount_kobo``; an odd
    first candidate gives None. ``currency`` is ``"NGN"`` only when that
    candidate had a Currency_Marker. ``any_odd`` is True when any non-balance
    candidate was odd, which makes the caller flag AMOUNT_FORMAT_ODD.
    """
    candidates = _find_amounts(text, balance_spans)
    if not candidates:
        return None, None, False
    first = candidates[0]
    amount = first.kobo if first.status == "ok" else None
    currency = "NGN" if first.has_marker else None
    return amount, currency, any(c.status != "ok" for c in candidates)


_WORD_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_WORD_SCALES = {"thousand": 1000, "million": 1_000_000}
_NUMBER_WORDS = set(_WORD_UNITS) | set(_WORD_SCALES) | {"hundred"}
_WORD_TOKEN_RE = re.compile(r"[a-z]+|[^a-z\s]")


def _words_to_int(words: list[str]) -> int | None:
    """Convert number words (``fifty thousand``) to an int, or None if empty or invalid."""
    total = current = 0
    seen = False
    for word in words:
        if word in ("and", "-"):
            continue
        seen = True
        if word in _WORD_UNITS:
            current += _WORD_UNITS[word]
        elif word == "hundred":
            current = max(current, 1) * 100
        elif word in _WORD_SCALES:
            total += max(current, 1) * _WORD_SCALES[word]
            current = 0
        else:
            return None
    return total + current if seen else None


def _amount_words_kobo(text: str) -> int | None:
    """Return the kobo value of the first Amount_In_Words, or None.

    Reads number words followed by ``naira``, with optional ``and <words> kobo``
    after it, for example ``fifty thousand naira``.
    """
    tokens = _WORD_TOKEN_RE.findall(text.lower())
    joiners = _NUMBER_WORDS | {"and", "-"}
    for i, token in enumerate(tokens):
        if token != "naira":
            continue
        j = i
        while j > 0 and tokens[j - 1] in joiners:
            j -= 1
        naira = _words_to_int([t for t in tokens[j:i]])
        if naira is None:
            continue
        kobo = 0
        k = i + 1
        if k < len(tokens) and tokens[k] == "and":
            k += 1
        end = k
        while end < len(tokens) and tokens[end] in _NUMBER_WORDS | {"-"}:
            end += 1
        if end > k and end < len(tokens) and tokens[end] == "kobo":
            part = _words_to_int(tokens[k:end])
            if part is not None:
                kobo = part
        return naira * 100 + kobo
    return None


def _collect_flags(codes: Iterable[str]) -> list[str]:
    """Return the unique known codes from ``codes`` in ``RED_FLAG_CODES`` order."""
    present = set(codes)
    return [code for code in RED_FLAG_CODES if code in present]


_PHONE_SENDER_RE = re.compile(r"\+?[0-9 \-]*")


def _sender_is_phone(sender_id: object) -> bool:
    """Phone_Number_Sender test.

    True when ``sender_id`` is a string made only of ASCII digits, spaces,
    hyphens and an optional leading ``+``, with 7 to 15 digits in total. The
    raw value is used, with no trimming. None, non-strings, empty and
    whitespace-only values are never phone senders.
    """
    if not isinstance(sender_id, str) or _PHONE_SENDER_RE.fullmatch(sender_id) is None:
        return False
    digits = sum(1 for ch in sender_id if ch in "0123456789")
    return 7 <= digits <= 15


def _sender_flags(sender_id: object) -> set[str]:
    """Flags derived from the sender_id alone."""
    flags: set[str] = set()
    if _sender_is_phone(sender_id):
        flags.add("SENDER_ID_MISMATCH")
    return flags


_PRESSURE_RES = tuple(
    re.compile(r"(?<!\w)" + re.escape(" ".join(phrase.lower().split())) + r"(?!\w)")
    for phrase in PRESSURE_PHRASES
)
_WHITESPACE_RUN_RE = re.compile(r"\s+")
# Curly quotes become straight ones before phrase matching.
_QUOTE_MAP = str.maketrans({"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"'})


def _has_pressure(text: str) -> bool:
    """True when ``text`` contains a Pressure_Phrase as whole words.

    Matching ignores letter case and treats any whitespace run as one space.
    A phrase inside a longer word does not match.
    """
    normalised = _normalise_text(text)
    return any(pattern.search(normalised) for pattern in _PRESSURE_RES)


def _normalise_text(text: str) -> str:
    """Straighten curly quotes, lower-case, and turn each whitespace run into one space."""
    return _WHITESPACE_RUN_RE.sub(" ", text.translate(_QUOTE_MAP).lower())


def _whole_word_re(phrase: str) -> re.Pattern[str]:
    """Compile a pattern that matches ``phrase`` only as whole words."""
    return re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)")


_TRANSFER_PHRASE_RES = tuple(_whole_word_re(p) for p in TRANSFER_REQUEST_PHRASES)
_REQUEST_WORDS_RE = _whole_word_re(_REQUEST_WORDS)
_TRANSFER_WORD_RE = _whole_word_re(_TRANSFER_WORD)


def _has_transfer_request(text: str) -> bool:
    """True when ``text`` says a transfer was requested rather than received.

    Matches a listed phrase, or the words ``request successful`` and
    ``transfer`` within 40 characters of each other. Case, curly quotes and
    whitespace runs are ignored, and words inside longer words do not count.
    """
    normalised = _normalise_text(text)
    if any(p.search(normalised) for p in _TRANSFER_PHRASE_RES):
        return True
    requests = [m.span() for m in _REQUEST_WORDS_RE.finditer(normalised)]
    transfers = [m.span() for m in _TRANSFER_WORD_RE.finditer(normalised)]
    return any(
        (t[0] - r[1] <= _NEAR_LIMIT) if t[0] >= r[1] else (r[0] - t[1] <= _NEAR_LIMIT)
        for r in requests
        for t in transfers
    )


_ACCOUNT_RE = re.compile(r"(?<![\d*])\d{3,4}\*{1,6}\d{3,4}(?![\d*])")
_NARRATION_RE = re.compile(
    r"(?<![A-Za-z])(?:narration|description|desc|remarks)(?![A-Za-z])"
    r"[ \t]*:?[ \t]*(?P<val>[^\r\n]*)",
    re.IGNORECASE,
)
_NARRATION_MAX = 200
_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z])(?:session[ \t]*id|ref[ \t]*no|reference|ref)(?![A-Za-z])"
    r"[ \t]*:?[ \t]*(?P<val>[A-Za-z0-9/\-]{4,50})(?![A-Za-z0-9/\-])",
    re.IGNORECASE,
)


def _find_account(text: str) -> tuple[str, Span] | None:
    """Return the first masked account (``012****789``) and its span, or None."""
    m = _ACCOUNT_RE.search(text)
    return (m.group(0), m.span()) if m else None


def _extract_account(text: str) -> str | None:
    """Return the first masked account exactly as written, or None."""
    found = _find_account(text)
    return found[0] if found else None


def _extract_narration(text: str) -> str | None:
    """Return the text after a narration label, to end of line, max 200 characters.

    The first label that is followed by non-blank text decides the result.
    """
    for m in _NARRATION_RE.finditer(text):
        value = m.group("val").strip()
        if value:
            return value[:_NARRATION_MAX].strip()
    return None


def _find_reference(text: str) -> tuple[str, Span] | None:
    """Return the first claimed reference and the span of its label and value."""
    m = _REFERENCE_RE.search(text)
    return (m.group("val"), m.span()) if m else None


def _extract_reference(text: str) -> str | None:
    """Return the identifier after a ``Ref``, ``Ref No``, ``Reference`` or ``Session ID`` label."""
    found = _find_reference(text)
    return found[0] if found else None


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# The time is optional: real alerts often put it on another line.
_DATE_TIME = r"(?!\d)(?:[ \t]+(?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?(?!\d))?"
_DATE_START = r"(?<![\d/\-A-Za-z])"
_MON = r"(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
# Each entry: (pattern, group order for (year, month, day)).
_DATE_LAYOUTS = (
    (re.compile(_DATE_START + r"(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})" + _DATE_TIME), "dmy"),
    (re.compile(_DATE_START + r"(?P<d>\d{1,2})-(?P<m>\d{1,2})-(?P<y>\d{4})" + _DATE_TIME), "dmy"),
    (re.compile(_DATE_START + r"(?P<d>\d{1,2})-" + _MON + r"-(?P<y>\d{4})" + _DATE_TIME, re.IGNORECASE), "mon"),
    (re.compile(_DATE_START + r"(?P<d>\d{1,2})[ \t]+" + _MON + r"[ \t]+(?P<y>\d{4})" + _DATE_TIME, re.IGNORECASE), "mon"),
    (re.compile(_DATE_START + r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})" + _DATE_TIME), "ymd"),
)
_DATE_SHAPE_RE = re.compile(_DATE_START + r"\d{1,4}[/-]\d{1,2}[/-]\d{1,4}(?!\d)")


def _scan_dates(text: str, masked_spans: Iterable[Span]) -> tuple[datetime | None, bool]:
    """Return ``(alert_time, date_odd)``.

    Matches the Recognised_Date_Formats followed by ``HH:MM[:SS]`` and checks
    them with ``datetime(...)``. A recognised layout with an impossible value
    is odd, and so is any other numeric date shape such as ``12/03/24``. A
    valid date with no time is not odd and gives ``alert_time`` None. A lone
    time is ignored. Matches overlapping ``masked_spans`` (account,
    reference, balance) are skipped. When any date is odd, ``alert_time`` is
    None.
    """
    masked = list(masked_spans)
    found: list[tuple[int, datetime | None, bool]] = []
    recognised: list[Span] = []
    for pattern, layout in _DATE_LAYOUTS:
        for m in pattern.finditer(text):
            if _overlaps(m.span(), masked) or _overlaps(m.span(), recognised):
                continue
            recognised.append(m.span())
            has_time = m.group("H") is not None
            try:
                month = _MONTHS[m.group("mon").lower()] if layout == "mon" else int(m.group("m"))
                value: datetime | None = datetime(
                    int(m.group("y")), month, int(m.group("d")),
                    int(m.group("H") or 0), int(m.group("M") or 0), int(m.group("S") or 0),
                )
                odd = False
                if not has_time:
                    value = None
            except ValueError:
                value, odd = None, True
            found.append((m.start(), value, odd))
    for m in _DATE_SHAPE_RE.finditer(text):
        if _overlaps(m.span(), masked) or _overlaps(m.span(), recognised):
            continue
        found.append((m.start(), None, True))
    if any(odd for _, _, odd in found):
        return None, True
    timed = [(start, value) for start, value, _ in found if value is not None]
    if not timed:
        return None, False
    return min(timed, key=lambda item: item[0])[1], False


_BANK_PATTERNS = tuple(
    (
        canonical,
        re.compile(
            r"(?<!\w)(?:"
            + "|".join(
                r"\s+".join(re.escape(w) for w in alias.split())
                for alias in sorted(aliases, key=len, reverse=True)
            )
            + r")(?!\w)",
            re.IGNORECASE,
        ),
    )
    for canonical, aliases in KNOWN_BANKS
)


def _first_bank(value: str) -> str | None:
    """Canonical name of the bank whose alias matches earliest in ``value``."""
    best: tuple[int, str] | None = None
    for canonical, pattern in _BANK_PATTERNS:
        m = pattern.search(value)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), canonical)
    return best[1] if best else None


def _extract_bank(text: str, sender_id: object) -> str | None:
    """Return the canonical name of the first known bank found.

    Aliases match on word boundaries, ignoring letter case. The text is
    searched first, and ``sender_id`` only when the text has no match. The
    earliest match wins.
    """
    bank = _first_bank(text)
    if bank is None and isinstance(sender_id, str):
        bank = _first_bank(sender_id)
    return bank


def _parse_body(text: str, sender_id: str | None) -> ParsedAlert:
    """Run every extractor independently on the normalised text."""
    flags = _sender_flags(sender_id)
    account = _find_account(text)
    reference = _find_reference(text)
    account_masked = account[0] if account else None
    narration = _extract_narration(text)
    claimed_reference = reference[0] if reference else None
    if _has_pressure(text):
        flags.add("PRESSURE_LANGUAGE")
    if _has_transfer_request(text):
        flags.add("TRANSFER_REQUEST_WORDING")
    balances = _balance_matches(text)
    available_balance_kobo = balances[0][1] if balances else None
    if not balances:
        flags.add("BALANCE_LINE_MISSING")
    amount_kobo, currency, any_odd = _extract_amount(text, [span for span, _ in balances])
    words_kobo = _amount_words_kobo(text)
    if any_odd or (
        words_kobo is not None and amount_kobo is not None and words_kobo != amount_kobo
    ):
        flags.add("AMOUNT_FORMAT_ODD")
    date_masks = [span for span, _ in balances]
    if account:
        date_masks.append(account[1])
    if reference:
        date_masks.append(reference[1])
    alert_time, date_odd = _scan_dates(text, date_masks)
    if date_odd:
        flags.add("DATE_ODD")
    return ParsedAlert(
        amount_kobo=amount_kobo,
        currency=currency,
        claimed_bank=_extract_bank(text, sender_id),
        sender_id=sender_id,
        account_masked=account_masked,
        narration=narration,
        alert_time=alert_time,
        available_balance_kobo=available_balance_kobo,
        claimed_reference=claimed_reference,
        red_flags=_collect_flags(flags),
    )


def parse_sms_alert(text: str, sender_id: str | None) -> ParsedAlert:
    """Parse a bank credit alert SMS and detect red flags.

    The function never raises. A non-string ``text`` is treated as the empty
    string. Text longer than 10,000 characters is truncated to its first
    10,000 characters before parsing, so anything after that point is ignored.
    ``sender_id`` is returned unchanged.
    """
    try:
        if not isinstance(text, str):
            text = ""
        text = text[:MAX_TEXT_LENGTH]
        return _parse_body(text, sender_id)
    except Exception:
        # Last-resort guard for totality: keep only the sender-derived flags.
        try:
            flags = _sender_flags(sender_id)
        except Exception:
            flags = set()
        return ParsedAlert(sender_id=sender_id, red_flags=_collect_flags(flags))
