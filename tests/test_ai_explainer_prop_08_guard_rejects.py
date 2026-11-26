"""Feature: ai-explainer, Property 8: Contradicting text is rejected."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.ai_explainer import guard_output

WRONG_CLAIMS = ["confirmed", "verified", "alive", "payment is real", "money is real",
                "payment is genuine", "money has arrived", "safe to release",
                "you can release", "payment went through"]
NEGATIVES = ["ghost", "fake", "forged", "suspicious"]
ALWAYS = ["fraudster", "scammer", "thief", "criminal", "lawyer", "legal action", "sue", "police"]
LABELS = {"CONFIRMED": "alive", "NOT_FOUND": "ghost", "SUSPICIOUS": "suspicious",
          "UNVERIFIED": "unverified"}

_plain = st.sampled_from(["Please take care.", "The date looks odd.", "Look at your bank app."])
_case = st.sampled_from(["lower", "upper", "title"])


def _apply(word: str, how: str) -> str:
    return word.upper() if how == "upper" else word.title() if how == "title" else word


def _insert(base: str, word: str, at: int) -> str:
    pos = at % (len(base) + 1)
    return f"{base[:pos]} {word} {base[pos:]}"


# **Validates: Requirements 5.5, 5.6, 5.7, 5.9**
@settings(max_examples=200, deadline=None)
@given(base=_plain, at=st.integers(0, 50), how=_case,
       code=st.sampled_from(["NOT_FOUND", "SUSPICIOUS", "UNVERIFIED"]),
       word=st.sampled_from(WRONG_CLAIMS))
def test_wrong_claims_rejected_when_not_confirmed(base, at, how, code, word) -> None:
    assert guard_output(_insert(base, _apply(word, how), at), code) is None


@settings(max_examples=100, deadline=None)
@given(base=_plain, at=st.integers(0, 50), how=_case, word=st.sampled_from(NEGATIVES))
def test_negative_words_rejected_when_confirmed(base, at, how, word) -> None:
    assert guard_output(_insert(base, _apply(word, how), at), "CONFIRMED") is None


@settings(max_examples=100, deadline=None)
@given(base=_plain, at=st.integers(0, 50), how=_case,
       code=st.sampled_from(list(LABELS)), word=st.sampled_from(ALWAYS))
def test_accusation_and_legal_words_rejected(base, at, how, code, word) -> None:
    assert guard_output(_insert(base, _apply(word, how), at), code) is None


@settings(max_examples=100, deadline=None)
@given(base=_plain, at=st.integers(0, 50), how=_case,
       code=st.sampled_from(list(LABELS)), other=st.sampled_from(list(LABELS)))
def test_other_verdict_labels_rejected(base, at, how, code, other) -> None:
    if other == code:
        return
    assert guard_output(_insert(base, _apply(LABELS[other], how), at), code) is None


@settings(max_examples=100, deadline=None)
@given(base=_plain, at=st.integers(0, 50), how=_case)
def test_unverified_alone_does_not_trigger_verified_rule(base, at, how) -> None:
    # "unverified" is the UNVERIFIED label itself, so it must pass for that code.
    text = _insert(base, _apply("unverified", how), at)
    assert guard_output(text, "UNVERIFIED") is not None
