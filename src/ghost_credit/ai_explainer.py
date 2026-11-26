"""Optional AI wording for replies: ``BedrockExplainer`` and ``get_explainer``.

Rules decide the verdict. The AI only rewords the reasons and risk notes. The
headline and the bank-app reminder always come from fixed code. The model never
sees the verdict code, red-flag code names, the amount, names, phone numbers or
account numbers. Any failure falls back to the ``TemplateExplainer`` text.
``boto3`` is imported only when a client is really needed, so this module and
its tests work without it.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from typing import Any, Mapping

from ghost_credit.parser import RED_FLAG_CODES
from ghost_credit.verdict import (
    CONFIRMED,
    FLAG_REASONS,
    NOT_FOUND,
    OWNER_LABELS,
    SUSPICIOUS,
    UNVERIFIED,
    Explainer,
    TemplateExplainer,
)

__all__ = ["BedrockExplainer", "get_explainer", "guard_output"]

MODEL_ID = "amazon.nova-micro-v1:0"
DEFAULT_REGION = "us-east-1"
MAX_TOKENS = 200
TIMEOUT_SECONDS = 5
MAX_OUTPUT_CHARS = 600
MAX_REASONS = 3
MAX_NOTES = 3
MAX_ITEM_CHARS = 160

SYSTEM_INSTRUCTION = (
    "You reword the points below for a shop owner reading on WhatsApp. "
    "Use plain, friendly English. Speak directly to the shop owner as 'you'. "
    "Write exactly 2 short sentences: first the reason, then what to do now. "
    "Never say 'we'. Never say anyone is investigating or looking into it. "
    "Never promise a follow-up or a later update. "
    "Talk about the alert, never about the customer, and do not accuse anyone. "
    "Do not say a screenshot or text message proves money is real. "
    "Do not give legal advice. "
    "Do not say whether to release goods. "
    "Do not add facts, names or numbers. "
    "Output the reworded text only."
)

_LOG = logging.getLogger("ghost_credit.ai_explainer")
_LAST_RESORT = "Check first before you release anything."
_FOUR_CODES = (CONFIRMED, NOT_FOUND, SUSPICIOUS, UNVERIFIED)
_MIN_SENSITIVE_LEN = 3
_PARSED_TEXT_FIELDS = (
    "currency",
    "claimed_bank",
    "sender_id",
    "account_masked",
    "narration",
    "claimed_reference",
    "screenshot_phash",
)
_DIGIT_GAP = re.compile(r"(?<=\d)[ ,.\-](?=\d)")
_LONG_DIGITS = re.compile(r"\d{7,}")
_SPACES = re.compile(r"\s+")


# --- Prompt sanitiser -----------------------------------------------------


def _is_int(value: object) -> bool:
    """True for a real int. A bool is refused because True == 1 in Python."""
    return isinstance(value, int) and not isinstance(value, bool)


def _add_digits(found: list[str], value: object) -> None:
    """Add the digits of a kobo amount, and of its whole-naira part, when long enough."""
    if not _is_int(value) or value < 0:  # type: ignore[operator]
        return
    for number in (value, value // 100):  # type: ignore[operator]
        digits = str(number)
        if len(digits) >= _MIN_SENSITIVE_LEN:
            found.append(digits)


def _sensitive_values(verdict: object, parsed: object) -> list[str]:
    """Collect lower-case strings that must never appear in the prompt.

    These are verdict codes, owner labels, red-flag codes, the alert's own
    text fields and the digits of its amounts.
    """
    found: list[str] = [c.lower() for c in _FOUR_CODES]
    found.extend(label.lower() for label in OWNER_LABELS.values())
    found.extend(c.lower() for c in RED_FLAG_CODES)
    found.extend(k.lower() for k in FLAG_REASONS)
    code = getattr(verdict, "code", None)
    if isinstance(code, str) and code.strip():
        found.append(code.strip().lower())
    flags = getattr(parsed, "red_flags", None)
    if isinstance(flags, list):
        found.extend(f.strip().lower() for f in flags if isinstance(f, str) and f.strip())
    for name in _PARSED_TEXT_FIELDS:
        value = getattr(parsed, name, None)
        if isinstance(value, str) and len(value.strip()) >= _MIN_SENSITIVE_LEN:
            found.append(value.strip().lower())
    _add_digits(found, getattr(parsed, "amount_kobo", None))
    _add_digits(found, getattr(parsed, "available_balance_kobo", None))
    return found


def _has_long_digits(text: str) -> bool:
    """True when the text has 7 or more digits in a row, ignoring gaps like spaces or commas."""
    return _LONG_DIGITS.search(_DIGIT_GAP.sub("", text)) is not None


def _is_clean(item: object, sensitive: list[str]) -> bool:
    """True when the item is a non-blank string with no sensitive text in it."""
    if not isinstance(item, str) or not item.strip():
        return False
    lowered = item.lower()
    if any(s in lowered for s in sensitive):
        return False
    return not _has_long_digits(item)


def _clean_items(items: object, sensitive: list[str], limit: int) -> list[str]:
    """Keep the first ``limit`` clean items in order, each cut to 160 characters."""
    if not isinstance(items, (list, tuple)):
        return []
    kept: list[str] = []
    for item in items:
        if len(kept) >= limit:
            break
        if _is_clean(item, sensitive):
            kept.append(_SPACES.sub(" ", item.strip())[:MAX_ITEM_CHARS].strip())  # type: ignore[union-attr]
    return kept


def _prompt_items(verdict: object, parsed: object, risk_notes: object) -> list[str]:
    """Return the reasons then the notes that may go into the prompt."""
    sensitive = _sensitive_values(verdict, parsed)
    reasons = _clean_items(getattr(verdict, "reasons", None), sensitive, MAX_REASONS)
    notes = _clean_items(risk_notes, sensitive, MAX_NOTES)
    return reasons + notes


# --- Output guard ---------------------------------------------------------

def _is_control(ch: str) -> bool:
    """True for control or format characters other than a newline."""
    if ch == "\n":
        return False
    return ch == "\x7f" or ch < " " or unicodedata.category(ch) in ("Cc", "Cf")


def _word_regex(phrase: str) -> re.Pattern[str]:
    """Whole-word, case-insensitive pattern for a word or a short phrase."""
    body = r"\s+".join(re.escape(part) for part in phrase.split())
    return re.compile(r"(?<!\w)" + body + r"(?!\w)", re.IGNORECASE)


_WRONG_CLAIMS = tuple(
    _word_regex(p)
    for p in (
        "confirmed",
        "verified",
        "alive",
        "payment is real",
        "money is real",
        "payment is genuine",
        "money has arrived",
        "safe to release",
        "you can release",
        "payment went through",
    )
)
_NEGATIVE_WORDS = tuple(_word_regex(p) for p in ("ghost", "fake", "forged", "suspicious"))
_ACCUSATION_WORDS = tuple(
    _word_regex(p)
    for p in (
        "fraudster",
        "scammer",
        "thief",
        "criminal",
        "lawyer",
        "legal action",
        "sue",
        "police",
    )
)
_BANNED_SUBSTRINGS = ("looking into", "investigat")
_BANNED_WORDS = tuple(_word_regex(p) for p in ("we", "we're", "we’re", "we'll", "we’ll", "our team"))
_LABEL_REGEX = {code: _word_regex(label) for code, label in OWNER_LABELS.items()}


def _clean_text(text: str) -> str:
    """Tidy control characters, newlines and spaces, then cut to 600 characters."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(" " if _is_control(ch) else ch for ch in text)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return _cut_text(text)


def _cut_text(text: str) -> str:
    """Cut at the last sentence end within 600 characters, else the last space."""
    best = -1
    for index in range(MAX_OUTPUT_CHARS):
        if text[index] in ".!?" and (
            index + 1 >= len(text) or text[index + 1] in " \n"
        ):
            best = index
    if best >= 0:
        return text[: best + 1].strip()
    space = text.rfind(" ", 0, MAX_OUTPUT_CHARS + 1)
    if space > 0:
        return text[:space].strip()
    return text[:MAX_OUTPUT_CHARS].strip()


def _contradicts(text: str, code: object) -> bool:
    """True when the text claims something the verdict code does not support."""
    key = code if code in _FOUR_CODES else UNVERIFIED
    lowered = text.lower()
    if any(s in lowered for s in _BANNED_SUBSTRINGS):
        return True
    if any(p.search(text) for p in _BANNED_WORDS):
        return True
    if key == CONFIRMED:
        if any(p.search(text) for p in _NEGATIVE_WORDS):
            return True
    elif any(p.search(text) for p in _WRONG_CLAIMS):
        return True
    for other, pattern in _LABEL_REGEX.items():
        if other != key and pattern.search(text):
            return True
    return any(p.search(text) for p in _ACCUSATION_WORDS)


def guard_output(text: object, code: object) -> str | None:
    """Return cleaned model text, or None when it must not be shown.

    Rejects non-text, blank text, wrong-verdict claims, accusations, legal
    words and long digit runs. Long text is cut to 600 characters.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    cleaned = _clean_text(text)
    if not cleaned:
        return None
    if _contradicts(cleaned, code) or _has_long_digits(cleaned):
        return None
    return cleaned


# --- BedrockExplainer -----------------------------------------------------


def _log_fallback(reason: str) -> None:
    """Write one log line holding only an exception type name or a fixed word."""
    _LOG.warning("ai explainer fallback: %s", reason)


class BedrockExplainer(Explainer):
    """Rewords reasons and notes with Amazon Bedrock, behind fixed code.

    The headline comes from ``TemplateExplainer``. Any failure returns the
    ``TemplateExplainer`` text. It never raises and makes at most one call.
    """

    def __init__(
        self,
        client: Any = None,
        region: str = DEFAULT_REGION,
        model_id: str = MODEL_ID,
    ) -> None:
        """Keep the optional client, the region and the model id."""
        self._client = client
        self._region = region
        self._model_id = model_id

    def _make_client(self) -> Any:
        """Create the bedrock-runtime client. boto3 is imported only here."""
        import boto3  # noqa: PLC0415 - lazy on purpose, so tests need no boto3
        from botocore.config import Config  # noqa: PLC0415

        config = Config(
            read_timeout=TIMEOUT_SECONDS,
            connect_timeout=TIMEOUT_SECONDS,
            retries={"max_attempts": 0},
        )
        return boto3.client("bedrock-runtime", region_name=self._region, config=config)

    def _request(self, items: list[str]) -> dict:
        """Build the Converse arguments: one system block and one user message."""
        points = "Points:\n" + "\n".join(f"- {item}" for item in items)
        return {
            "modelId": self._model_id,
            "system": [{"text": SYSTEM_INSTRUCTION}],
            "messages": [{"role": "user", "content": [{"text": points}]}],
            "inferenceConfig": {"maxTokens": MAX_TOKENS},
        }

    @staticmethod
    def _read_text(response: object) -> object:
        """Return output.message.content[0].text, or None for any other shape."""
        try:
            return response["output"]["message"]["content"][0]["text"]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return None

    def explain(self, verdict: Any, parsed: Any, risk_notes: Any) -> str:
        """Return headline, a blank line and guarded AI text; else the template text."""
        try:
            fallback = TemplateExplainer().explain(verdict, parsed, risk_notes)
        except Exception as exc:  # noqa: BLE001 - explain must never raise
            _log_fallback(type(exc).__name__)
            return _LAST_RESORT
        try:
            items = _prompt_items(verdict, parsed, risk_notes)
            if not items:
                _log_fallback("NoUsableText")
                return fallback
            if self._client is None:
                self._client = self._make_client()
            response = self._client.converse(**self._request(items))
            raw = self._read_text(response)
            if not isinstance(raw, str):
                _log_fallback("NoUsableText")
                return fallback
            text = guard_output(raw, getattr(verdict, "code", None))
            if text is None:
                _log_fallback("GuardRejected")
                return fallback
            headline = fallback.split("\n", 1)[0]
            return f"{headline}\n\n{text}"
        except Exception as exc:  # noqa: BLE001 - any failure means the safe text
            _log_fallback(type(exc).__name__)
            return fallback


# --- Factory --------------------------------------------------------------


def get_explainer(env: Mapping[str, str] | None = None, client: Any = None) -> Explainer:
    """Return BedrockExplainer only when EXPLAINER is 'bedrock'; else the template one.

    Reads no boto3 and contacts no network. It never raises.
    """
    try:
        source = os.environ if env is None else env
        value = source.get("EXPLAINER")
        if isinstance(value, str) and value.strip().lower() == "bedrock":
            return BedrockExplainer(client=client)
    except Exception:  # noqa: BLE001 - a broken mapping means the free default
        pass
    return TemplateExplainer()
