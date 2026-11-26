"""Shared fakes and strategies for the AI explainer tests. Synthetic data only."""

from __future__ import annotations

from typing import Any

from hypothesis import strategies as st

from ghost_credit.parser import RED_FLAG_CODES, ParsedAlert
from ghost_credit.pattern_network import Verdict

CODES = ("CONFIRMED", "NOT_FOUND", "SUSPICIOUS", "UNVERIFIED")

# Synthetic alert values the prompt must never contain.
SYNTH_ACCOUNT = "012****789"
SYNTH_NARRATION = "Test Sender Ada"
SYNTH_AMOUNT = 4500000


class ReadTimeoutError(Exception):
    """Stands in for botocore's timeout error. Only the class name matters."""


class FakeClient:
    """A fake bedrock-runtime client. It records calls and never uses a network.

    Modes: ``reply`` (returns ``text``), ``bad_shape``, ``non_text``,
    ``raise`` (raises ``exc``).
    """

    def __init__(self, mode: str = "reply", text: Any = "Ok.", exc: Exception | None = None):
        self.mode = mode
        self.text = text
        self.exc = exc or RuntimeError("boom")
        self.calls: list[dict] = []

    def converse(self, **kwargs: Any) -> Any:
        """Record the call and answer by mode."""
        self.calls.append(kwargs)
        if self.mode == "raise":
            raise self.exc
        if self.mode == "bad_shape":
            return {"output": {"message": {"content": []}}}
        if self.mode == "non_text":
            return {"output": {"message": {"content": [{"text": 123}]}}}
        return {"output": {"message": {"content": [{"text": self.text}]}}}


def reply_with(text: Any) -> dict:
    """A recorded Converse response shape holding ``text``."""
    return {"output": {"message": {"content": [{"text": text}]}}}


def make_verdict(code: str = "SUSPICIOUS", reasons: list | None = None) -> Verdict:
    """Build a real Verdict with the given code and reasons."""
    return Verdict(code=code, paystack_checked=code in ("CONFIRMED", "NOT_FOUND"),
                   reasons=list(reasons if reasons is not None else ["The date looks wrong."]))


def make_parsed(**overrides: Any) -> ParsedAlert:
    """Build a synthetic ParsedAlert with an amount and an account."""
    values: dict[str, Any] = dict(
        amount_kobo=SYNTH_AMOUNT,
        currency="NGN",
        claimed_bank="Test Bank",
        sender_id="TESTBANK",
        account_masked=SYNTH_ACCOUNT,
        narration=SYNTH_NARRATION,
        available_balance_kobo=9900000,
        claimed_reference="REF123456",
        red_flags=["DATE_ODD"],
    )
    values.update(overrides)
    return ParsedAlert(**values)


_SAFE_TEXT = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu"), max_codepoint=0x7A),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip() != "")

SENSITIVE_SNIPPETS = (
    "SUSPICIOUS",
    "not_found",
    "DATE_ODD",
    "SENDER_ID_MISMATCH",
    SYNTH_ACCOUNT,
    SYNTH_NARRATION,
    "4500000",
    "45000",
    "08012345678",
    "0801 234 5678",
    "GHOST",
)

codes = st.sampled_from(CODES)
flag_codes = st.sampled_from(RED_FLAG_CODES)

reason_text = st.one_of(
    _SAFE_TEXT,
    st.tuples(_SAFE_TEXT, st.sampled_from(SENSITIVE_SNIPPETS), _SAFE_TEXT).map(
        lambda t: f"{t[0]} {t[1]} {t[2]}"
    ),
)
reasons_list = st.lists(st.one_of(reason_text, st.integers(), st.none()), max_size=8)
notes_list = st.lists(st.one_of(reason_text, st.integers()), max_size=8)

client_modes = st.sampled_from(["reply", "bad_shape", "non_text", "raise", "timeout"])


def client_for(mode: str, text: str = "Take care with this alert.") -> FakeClient:
    """Build a FakeClient for a mode name used by ``client_modes``."""
    if mode == "timeout":
        return FakeClient("raise", exc=ReadTimeoutError("slow"))
    return FakeClient(mode, text=text)
