"""Shared fakes and generators for The Lab tests. Synthetic data only.

No AWS, no network, no Paystack, no AI model. Nothing here imports boto3.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from hypothesis import strategies as st

from ghost_credit.parser import RED_FLAG_CODES, ParsedAlert
from ghost_credit.paystack import UNAVAILABLE, PaystackResult
from ghost_credit.pattern_network import Verdict
from ghost_credit.pipeline import CheckResult

LAGOS = timezone(timedelta(hours=1))
FIXED_NOW = datetime(2026, 11, 20, 10, 2, 11, tzinfo=LAGOS)
CODES = ["CONFIRMED", "NOT_FOUND", "SUSPICIOUS", "UNVERIFIED"]


# --- Fakes ----------------------------------------------------------------


class FakeDynamoClient:
    """A low-level DynamoDB client double that records every call."""

    def __init__(self, items: list[dict] | None = None) -> None:
        self.puts: list[dict] = []
        self.scans: list[dict] = []
        self.items = items or []

    def put_item(self, **kwargs: Any) -> dict:
        """Record the call."""
        self.puts.append(kwargs)
        return {}

    def scan(self, **kwargs: Any) -> dict:
        """Record the call and return the prepared items."""
        self.scans.append(kwargs)
        return {"Items": list(self.items)}


class RaisingStore:
    """A store whose save always raises the given exception."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    def save(self, record: dict) -> None:
        """Raise."""
        self.calls += 1
        raise self.exc

    def newest(self, limit: int) -> list[dict]:
        """Raise."""
        raise self.exc


class SpyStore:
    """A store that keeps what it was given, in order."""

    def __init__(self) -> None:
        self.saved: list[dict] = []

    def save(self, record: dict) -> None:
        """Keep the record."""
        self.saved.append(record)

    def newest(self, limit: int) -> list[dict]:
        """Return the newest records first."""
        return self.saved[::-1][:limit]


class FakeRunCheck:
    """A fake run_check: records calls, returns a given CheckResult, can raise."""

    def __init__(self, result: CheckResult | None = None, raises: bool = False) -> None:
        self.result = result if result is not None else make_result()
        self.raises = raises
        self.calls: list[tuple] = []
        self.kwargs: list[dict] = []

    def __call__(self, text, sender_id, image_bytes, category, now, **kwargs):
        self.calls.append((text, sender_id, image_bytes, category, now))
        self.kwargs.append(kwargs)
        if self.raises:
            raise RuntimeError("fake check failure")
        return self.result


def make_result(
    code: str = "SUSPICIOUS",
    amount_kobo: int | None = 4500000,
    flags: list[str] | None = None,
    reasons: list[str] | None = None,
    notes: list[str] | None = None,
    bank: str | None = "GTBank",
    reply: str = "Hold the goods.\nCheck your own bank app before releasing goods.",
    check_id: str = "check-0001",
) -> CheckResult:
    """Build one synthetic CheckResult."""
    verdict = Verdict(
        code=code,
        paystack_checked=code in ("CONFIRMED", "NOT_FOUND"),
        decided_by="rules",
        owner_outcome="unknown",
        reasons=list(reasons if reasons is not None else ["A reason."]),
    )
    parsed = ParsedAlert(
        amount_kobo=amount_kobo,
        claimed_bank=bank,
        red_flags=list(flags if flags is not None else []),
    )
    paystack = PaystackResult(UNAVAILABLE, False, None, None, None, "could not check Paystack")
    return CheckResult(
        check_id=check_id,
        parsed=parsed,
        paystack_result=paystack,
        verdict=verdict,
        reply=reply,
        risk_notes=list(notes if notes is not None else []),
    )


# --- Strategies -----------------------------------------------------------

words = st.text(alphabet="abcdefghij KLMNO.,-", min_size=0, max_size=40)
any_text = st.text(max_size=200)
safe_ids = st.text(alphabet="abcdef0123456789-", min_size=1, max_size=36)
lagos_times = st.datetimes(
    min_value=datetime(2001, 1, 1), max_value=datetime(2099, 1, 1)
).map(lambda d: d.replace(tzinfo=LAGOS, microsecond=0))
nows = st.one_of(
    st.datetimes(min_value=datetime(2001, 1, 1), max_value=datetime(2099, 1, 1)),
    st.builds(
        lambda d, m: d.replace(tzinfo=timezone(timedelta(minutes=m))),
        st.datetimes(min_value=datetime(2001, 1, 1), max_value=datetime(2099, 1, 1)),
        st.integers(min_value=-12 * 60, max_value=14 * 60),
    ),
)

# Digit runs of the kinds that must never be saved.
_separators = st.sampled_from(["", " ", "-", ".", ",", " - "])
digit_runs = st.builds(
    lambda digits, seps: "".join(d + s for d, s in zip(digits, seps)),
    st.lists(st.sampled_from("0123456789"), min_size=7, max_size=16),
    st.lists(_separators, min_size=16, max_size=16),
)
phone_like = st.builds(
    lambda pre, run: pre + run,
    st.sampled_from(["", "+", "+234 ", "0", "012****"]),
    digit_runs,
)
text_with_digits = st.lists(st.one_of(words, phone_like), min_size=1, max_size=5).map(
    " ".join
)

valid_records = st.fixed_dictionaries(
    {
        "check_id": safe_ids,
        "checked_at": lagos_times.map(lambda d: d.isoformat(timespec="seconds")),
        "channel": st.sampled_from(["whatsapp", "lab"]),
        "verdict": st.sampled_from(CODES),
        "owner_label": st.sampled_from(["ALIVE", "GHOST", "SUSPICIOUS", "UNVERIFIED"]),
        "amount_kobo": st.one_of(st.none(), st.integers(min_value=0, max_value=10**10)),
        "claimed_bank": st.one_of(st.none(), words),
        "red_flags": st.lists(st.sampled_from(list(RED_FLAG_CODES)), max_size=5),
        "reasons": st.lists(words, max_size=5),
        "risk_notes": st.lists(words, max_size=5),
        "expires_at": st.integers(min_value=0, max_value=4_000_000_000),
    }
)

check_results = st.builds(
    make_result,
    code=st.sampled_from(CODES),
    amount_kobo=st.one_of(st.none(), st.integers(min_value=0, max_value=10**10)),
    flags=st.lists(st.sampled_from(list(RED_FLAG_CODES)), max_size=4),
    reasons=st.lists(any_text, min_size=1, max_size=15),
    notes=st.lists(any_text, max_size=15),
    bank=st.one_of(st.none(), any_text),
    reply=any_text,
    check_id=safe_ids,
)
