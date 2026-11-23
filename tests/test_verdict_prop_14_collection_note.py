"""Feature: verdict-engine, Property 14: Collection note follows whole-word matching."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import ParsedAlert
from ghost_credit.verdict import risk_notes

NOTE = (
    "Someone is coming to collect at once. "
    "Do not release goods until the money shows in your bank app."
)

_filler_words = st.sampled_from(
    ["ok", "paid", "ngn", "sent", "it\u2019s", "\u201chello\u201d", "thanks"]
)
_space = st.text(alphabet=" \t\n", min_size=1, max_size=3)
_terms = st.sampled_from(["rider", "dispatch", "driver", "pick up now", "pickup now"])
_cases = st.sampled_from(["lower", "upper", "title", "swap"])


def _recase(text: str, how: str) -> str:
    return {"lower": text.lower(), "upper": text.upper(),
            "title": text.title(), "swap": text.swapcase()}[how]


@st.composite
def _text_with(draw, term_form):
    """Filler words, with one term form placed between runs of whitespace."""
    before = draw(st.lists(_filler_words, max_size=4))
    after = draw(st.lists(_filler_words, max_size=4))
    parts = before + [term_form] + after
    seps = [draw(_space) for _ in parts]
    return "".join(p + s for p, s in zip(parts, seps))


@st.composite
def _positive(draw):
    term = draw(_terms)
    how = draw(_cases)
    words = _recase(term, how).split(" ")
    glue = [draw(_space) for _ in words]
    form = "".join(w + (g if i < len(words) - 1 else "")
                   for i, (w, g) in enumerate(zip(words, glue)))
    return draw(_text_with(form))


@st.composite
def _negative(draw):
    form = draw(st.sampled_from(["drivers", "riderless", "xdispatch", "pickups now",
                                 "pick-up-now", "redriver", "dispatching"]))
    return draw(_text_with(form))


@settings(max_examples=200)
@given(text=_positive())
def test_whole_word_present_gives_note(text) -> None:
    """**Validates: Requirements 5.5, 5.6**"""
    assert NOTE in risk_notes(ParsedAlert(), alert_text=text)


@settings(max_examples=200)
@given(text=_negative())
def test_term_inside_longer_word_gives_no_note(text) -> None:
    """**Validates: Requirements 5.5, 5.6**"""
    assert NOTE not in risk_notes(ParsedAlert(), alert_text=text)


@settings(max_examples=100)
@given(value=st.one_of(st.none(), st.integers(), st.lists(st.text(max_size=5), max_size=3)))
def test_non_string_text_gives_no_note(value) -> None:
    """**Validates: Requirements 5.7**"""
    assert risk_notes(ParsedAlert(), alert_text=value) == []  # type: ignore[arg-type]
