"""Example tests for lab.py: store factory, formatting, flags, page source."""

from __future__ import annotations

import re

import pytest

from ghost_credit.lab import (
    DynamoCheckStore,
    InMemoryCheckStore,
    format_naira,
    get_store,
    plain_english_flags,
    record_check,
    render_page,
    sanitise_record,
)
from ghost_credit.pipeline import FLAG_ORDER
from ghost_credit.verdict import FLAG_REASONS
from lab_fakes import FIXED_NOW, make_result


def test_get_store_none_without_env(monkeypatch):
    monkeypatch.delenv("CHECKS_TABLE", raising=False)
    assert get_store() is None


def test_get_store_dynamo_with_env(monkeypatch):
    monkeypatch.setenv("CHECKS_TABLE", "some-table")
    assert isinstance(get_store(), DynamoCheckStore)


def test_dynamo_store_does_not_import_boto3_at_creation(monkeypatch):
    monkeypatch.setenv("CHECKS_TABLE", "some-table")
    import sys

    sys.modules.pop("boto3", None)
    get_store()
    assert "boto3" not in sys.modules


def test_record_check_with_no_store_does_nothing():
    assert record_check(None, make_result(), "lab", FIXED_NOW) is None


def test_saved_record_has_no_message_text_or_numbers():
    store = InMemoryCheckStore()
    result = make_result(
        reasons=["Sender 08031234567 pushed."], notes=["Acct 0123456789 odd."], bank="GTBank 0123456789"
    )
    record_check(store, result, "lab", FIXED_NOW)
    saved = store.newest(1)[0]
    text = str(saved)
    assert "08031234567" not in text and "0123456789" not in text
    assert "[removed]" in text
    assert saved["checked_at"] == "2026-11-20T10:02:11+01:00"


def test_checked_at_timestamp_is_not_masked():
    out = sanitise_record({"check_id": "x", "checked_at": "2026-11-20T10:02:11+01:00"})
    assert out["checked_at"] == "2026-11-20T10:02:11+01:00"


def test_six_digit_numbers_are_kept():
    out = sanitise_record({"reasons": ["ref 123456 and 4,500.00"]})
    assert out["reasons"] == ["ref 123456 and 4,500.00"]


@pytest.mark.parametrize(
    "kobo,expected",
    [(0, "NGN 0.00"), (4500000, "NGN 45,000.00"), (50, "NGN 0.50"), (None, "Amount not read")],
)
def test_format_naira(kobo, expected):
    assert format_naira(kobo) == expected


@pytest.mark.parametrize("code", FLAG_ORDER)
def test_plain_english_flags_for_every_code(code):
    assert plain_english_flags([code]) == [FLAG_REASONS[code]]


def test_plain_english_flags_drops_unknown():
    assert plain_english_flags(["NOPE", "DATE_ODD"]) == [FLAG_REASONS["DATE_ODD"]]


def test_page_is_self_contained():
    page = render_page()
    assert "http://" not in page and "https://" not in page
    assert not re.search(r"<script[^>]*\ssrc=", page)
    assert not re.search(r"<link[^>]*href=", page)
    assert not re.search(r"\s(src|href)\s*=", page)
    assert '<meta name="viewport"' in page
    assert "<style>" in page and "<script>" in page
    assert "/lab/data" in page
    assert 'action="/lab/check"' in page


@pytest.mark.parametrize(
    "banned", ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"]
)
def test_page_js_avoids_unsafe_apis(banned):
    assert banned not in render_page()


def test_page_has_filter_and_sample_toggle_and_styles():
    page = render_page()
    assert 'id="filter"' in page and 'id="sample-toggle"' in page
    assert ".ghost" in page and ".alive" in page
    assert "textContent" in page and "createElement" in page
