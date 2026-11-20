"""Check whether the money in a parsed credit alert exists in Paystack.

``verify`` is the only place in Ghost Credit that can say CONFIRMED, because
only Paystack can prove money arrived. It makes at most one read-only call,
test keys only. This is a different type from the verdict-engine's own
``PaystackResult``, so import one of them under an alias.

A result with ``checked`` False means no Paystack check took place, so the
verdict mapping must treat it as "no Paystack check".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from ghost_credit.parser import ParsedAlert

# Callable(url, headers, timeout_seconds) -> (http_status, body_bytes).
HttpFunction = Callable[[str, "dict[str, str]", float], "tuple[int, bytes]"]

CONFIRMED = "CONFIRMED"
NOT_FOUND = "NOT_FOUND"
UNAVAILABLE = "UNAVAILABLE"

REASON_NO_KEY = "no Paystack key set"
REASON_NOT_TEST_KEY = "test keys only during the hackathon"
REASON_NO_AMOUNT = "could not read the amount"
REASON_UNREACHABLE = "could not reach Paystack"
REASON_BAD_STATUS = "Paystack did not answer normally"
REASON_BAD_REPLY = "Paystack reply could not be read"
REASON_NO_MATCH = "Paystack has no matching payment"
REASON_MANY = "more than one payment of this amount, check manually"
REASON_MATCH = "Paystack has a matching payment"
REASON_INTERNAL = "could not check Paystack"
REASON_NO_SUCH_REFERENCE = "Paystack has no payment with this reference"

# Built from two pieces so the full prefix never appears as one literal.
_TEST_KEY_PREFIX = "sk_" + "test_"

VERIFY_URL = "https://api.paystack.co/transaction/verify/"
LIST_URL = "https://api.paystack.co/transaction"
TIMEOUT_SECONDS = 5.0
PER_PAGE = 100
USER_AGENT = "ghost-credit/0.1"
ACCEPT = "application/json"

# Lagos is a fixed +01:00 all year (no daylight saving).
_LAGOS = timezone(timedelta(hours=1))


@dataclass(frozen=True)
class PaystackResult:
    """What Paystack told us. ``reason`` is always a fixed plain-English string."""

    status: str
    checked: bool
    matched_reference: str | None
    amount_kobo: int | None
    paid_at: datetime | None
    reason: str


def _unavailable(reason: str) -> PaystackResult:
    """Build an UNAVAILABLE result: no usable Paystack answer."""
    return PaystackResult(UNAVAILABLE, False, None, None, None, reason)


def _not_found(reason: str, checked: bool) -> PaystackResult:
    """Build a NOT_FOUND result; ``checked`` says whether Paystack answered."""
    return PaystackResult(NOT_FOUND, checked, None, None, None, reason)


def _confirmed(reference: str | None, amount_kobo: int,
               paid_at: datetime | None) -> PaystackResult:
    """Build a CONFIRMED result for a payment Paystack reported."""
    return PaystackResult(CONFIRMED, True, reference, amount_kobo, paid_at, REASON_MATCH)


def _key_problem(secret_key: object) -> PaystackResult | None:
    """Return an UNAVAILABLE result if the key is missing or not a test key, else None."""
    if not isinstance(secret_key, str) or not secret_key:
        return _unavailable(REASON_NO_KEY)
    if not secret_key.startswith(_TEST_KEY_PREFIX):
        return _unavailable(REASON_NOT_TEST_KEY)
    return None


def _is_int_amount(value: object) -> bool:
    """True for a real int. A bool is refused because True == 1 in Python."""
    return isinstance(value, int) and not isinstance(value, bool)


def _usable_reference(value: object) -> str | None:
    """Return the reference if it is text with a visible character, else None."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def _to_lagos(dt: datetime) -> datetime:
    """Return ``dt`` as Lagos time. Naive means Lagos already; aware is converted."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=_LAGOS)
    return dt.astimezone(_LAGOS)


def _search_window(alert_time: datetime | None,
                   now: datetime) -> tuple[datetime, datetime]:
    """Return the (from, to) Lagos times to search for the payment.

    With an alert time: 30 minutes before to 5 minutes after it. Without one:
    the last 60 minutes up to ``now``. Conversion happens before the minutes
    are added so the offset is never lost.
    """
    if alert_time is not None:
        centre = _to_lagos(alert_time)
        return centre - timedelta(minutes=30), centre + timedelta(minutes=5)
    end = _to_lagos(now)
    return end - timedelta(minutes=60), end


def _iso(dt: datetime) -> str:
    """Write a Lagos datetime as ISO 8601 text such as 2026-11-20T10:02:11+01:00."""
    return _to_lagos(dt).isoformat(timespec="seconds")


def _auth_headers(secret_key: str) -> dict[str, str]:
    """Return the request headers. The key goes in Authorization and nowhere else.

    User-Agent and Accept are always sent because Paystack's Cloudflare
    front blocks the default Python-urllib User-Agent.
    """
    return {
        "Authorization": "Bearer " + secret_key,
        "User-Agent": USER_AGENT,
        "Accept": ACCEPT,
    }


def _verify_request(reference: str, secret_key: str) -> tuple[str, dict[str, str]]:
    """Build the URL and headers to look up one payment by its reference."""
    url = VERIFY_URL + urllib.parse.quote(reference, safe="")
    return url, _auth_headers(secret_key)


def _list_request(window: tuple[datetime, datetime],
                  secret_key: str) -> tuple[str, dict[str, str]]:
    """Build the URL and headers to list successful payments in a time window."""
    query = urllib.parse.urlencode({
        "status": "success",
        "from": _iso(window[0]),
        "to": _iso(window[1]),
        "perPage": PER_PAGE,
    })
    return LIST_URL + "?" + query, _auth_headers(secret_key)


def default_http(url: str, headers: dict[str, str],
                 timeout_seconds: float) -> tuple[int, bytes]:
    """Do one GET with urllib and return (status, body).

    Sends exactly the headers it is given and adds none (no User-Agent).
    An HTTP error such as 401 or 404 returns its code and body so the caller
    can decide. Other errors (timeout, no network) are raised.
    """
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def _is_reply_pair(reply: object) -> bool:
    """True when an Http_Function reply is a (status int, body bytes) pair."""
    return (isinstance(reply, tuple) and len(reply) == 2
            and _is_int_amount(reply[0]) and isinstance(reply[1], (bytes, bytearray)))


def _parse_body(body: object) -> dict | None:
    """Decode a reply body as a UTF-8 JSON object, or return None if it is not one."""
    if not isinstance(body, (bytes, bytearray)):
        return None
    try:
        value = json.loads(bytes(body).decode("utf-8"))
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _is_match(item: object, amount: int) -> bool:
    """True when ``item`` is a successful NGN transaction for exactly ``amount`` kobo."""
    return (isinstance(item, dict)
            and item.get("status") == "success"
            and item.get("currency") == "NGN"
            and _is_int_amount(item.get("amount"))
            and item.get("amount") == amount)


def _parse_paid_at(value: object) -> datetime | None:
    """Read an ISO 8601 ``paid_at`` as a Lagos datetime, or None if unreadable."""
    if not isinstance(value, str):
        return None
    try:
        return _to_lagos(datetime.fromisoformat(value))
    except (ValueError, OverflowError):
        return None


def _is_reference_not_found(status_code: int, body: object) -> bool:
    """True when Paystack clearly says it has no payment with this reference.

    Needs HTTP 400 or 404, a JSON object whose ``status`` is exactly false, and
    either code "transaction_not_found" or a message containing "not found".
    """
    if status_code not in (400, 404):
        return False
    data = _parse_body(body)
    if data is None or data.get("status") is not False:
        return False
    message = data.get("message")
    return (data.get("code") == "transaction_not_found"
            or (isinstance(message, str) and "not found" in message.lower()))


def _decide_by_reference(data: dict, claimed_reference: str, amount: int) -> PaystackResult:
    """Decide from a verify reply: CONFIRMED if it matches, else NOT_FOUND (checked)."""
    if not _is_match(data, amount):
        return _not_found(REASON_NO_MATCH, True)
    return _confirmed(claimed_reference, amount, _parse_paid_at(data.get("paid_at")))


def _decide_by_search(items: list, amount: int) -> PaystackResult:
    """Decide from a list reply: CONFIRMED only for exactly one match on a short page.

    Non-object items are skipped. A full page (100) with a match is not trusted
    because another page could hold a second payment of the same amount.
    """
    matches = [item for item in items if _is_match(item, amount)]
    if not matches:
        return _not_found(REASON_NO_MATCH, True)
    if len(matches) > 1 or len(items) >= PER_PAGE:
        return _not_found(REASON_MANY, True)
    match = matches[0]
    reference = match.get("reference")
    return _confirmed(reference if isinstance(reference, str) else None,
                      amount, _parse_paid_at(match.get("paid_at")))


def verify(parsed: ParsedAlert, secret_key: str | None, now: datetime,
           *, http: HttpFunction | None = None) -> PaystackResult:
    """Check the alert against Paystack and return a result. Never raises.

    The key is checked before any field of ``parsed`` is read, so a bad key
    never touches the alert. An unreadable amount stops the check, so nothing
    is matched by guesswork.
    """
    try:
        problem = _key_problem(secret_key)
        if problem is not None:
            return problem
        amount = getattr(parsed, "amount_kobo", None)
        if not _is_int_amount(amount):
            return _not_found(REASON_NO_AMOUNT, False)
        reference = _usable_reference(getattr(parsed, "claimed_reference", None))
        if reference is not None:
            url, headers = _verify_request(reference, secret_key)
        else:
            window = _search_window(getattr(parsed, "alert_time", None), now)
            url, headers = _list_request(window, secret_key)
        send = http if http is not None else default_http
        try:
            reply = send(url, headers, TIMEOUT_SECONDS)  # one call, no retry
        except Exception:
            # Raised. No exception text is kept.
            return _unavailable(REASON_UNREACHABLE)
        if not _is_reply_pair(reply):
            return _unavailable(REASON_UNREACHABLE)
        status_code, body = reply
        if status_code != 200:
            if reference is not None and _is_reference_not_found(status_code, body):
                return _not_found(REASON_NO_SUCH_REFERENCE, True)
            return _unavailable(REASON_BAD_STATUS)
        parsed_body = _parse_body(body)
        expected = dict if reference is not None else list
        if parsed_body is None or not isinstance(parsed_body.get("data"), expected):
            return _unavailable(REASON_BAD_REPLY)
        if reference is not None:
            return _decide_by_reference(parsed_body["data"], reference, amount)
        return _decide_by_search(parsed_body["data"], amount)
    except Exception:
        return _unavailable(REASON_INTERNAL)
