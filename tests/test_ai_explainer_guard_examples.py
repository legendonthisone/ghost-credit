"""Examples for the AI explainer output guard."""

from __future__ import annotations

from ghost_credit.ai_explainer import guard_output


def test_payment_is_real_rejected_for_suspicious() -> None:
    assert guard_output("Your payment is real.", "SUSPICIOUS") is None


def test_unverified_word_allowed_for_unverified() -> None:
    assert guard_output("This alert is unverified so far.", "UNVERIFIED") == "This alert is unverified so far."


def test_long_text_cut_at_sentence_end() -> None:
    sentence = "This alert has a warning sign. "
    out = guard_output(sentence * 30, "SUSPICIOUS")
    assert out is not None
    assert len(out) <= 600
    assert out.endswith(".")
    assert out == (sentence * 30)[: len(out)].rstrip()


def test_long_text_without_sentence_end_cut_at_space() -> None:
    out = guard_output("word " * 300, "SUSPICIOUS")
    assert out is not None and len(out) <= 600 and out.endswith("word")


def test_control_characters_become_spaces_and_newlines_squeezed() -> None:
    assert guard_output("a\x00b\x07c\n\n\n\nd", "UNVERIFIED") == "a b c\n\nd"


def test_blank_and_non_text_rejected() -> None:
    assert guard_output("   \n ", "UNVERIFIED") is None
    assert guard_output(None, "UNVERIFIED") is None
    assert guard_output(["x"], "UNVERIFIED") is None


def test_long_digit_run_rejected() -> None:
    assert guard_output("Call 0801 234 5678 now", "UNVERIFIED") is None
