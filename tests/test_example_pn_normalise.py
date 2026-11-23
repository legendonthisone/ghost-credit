"""Example tests for the payer-detail normaliser (synthetic values only)."""

from __future__ import annotations

from ghost_credit.pattern_network import normalise_account, normalise_name, normalise_phone


def test_phone_with_spaces() -> None:
    assert normalise_phone("0803 123 4567") == "+2348031234567"


def test_name_with_punctuation() -> None:
    assert normalise_name("  ada   o'neil-okafor, Jr. ") == "ADA ONEILOKAFOR JR"


def test_masked_account_is_none() -> None:
    assert normalise_account("012****789") is None


def test_nine_digit_account_is_none() -> None:
    assert normalise_account("012345678") is None


def test_nine_subscriber_digit_phone_is_none() -> None:
    assert normalise_phone("0803123456") is None
