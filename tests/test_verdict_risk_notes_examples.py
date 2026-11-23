"""Examples: each risk note, including the edges of Friday, the threshold and the text."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ghost_credit.verdict import risk_notes
from verdict_helpers import make_parsed

WEEKEND = "Sent late on a Friday or at the weekend, a common time for fake alerts."
LARGE = "Large amount. Take extra care before releasing goods."
COLLECT = (
    "Someone is coming to collect at once. "
    "Do not release goods until the money shows in your bank app."
)

# 2026-11-20 is a Friday.
FRIDAY = datetime(2026, 11, 20)


def _notes(when: datetime | None) -> list[str]:
    return risk_notes(make_parsed(alert_time=when))


def test_friday_1359_no_note() -> None:
    assert _notes(FRIDAY.replace(hour=13, minute=59)) == []


def test_friday_1400_note() -> None:
    assert _notes(FRIDAY.replace(hour=14)) == [WEEKEND]


def test_saturday_and_sunday_note() -> None:
    assert _notes(datetime(2026, 11, 21, 9, 0)) == [WEEKEND]
    assert _notes(datetime(2026, 11, 22, 9, 0)) == [WEEKEND]


def test_monday_and_thursday_no_note() -> None:
    assert _notes(datetime(2026, 11, 23, 9, 0)) == []
    assert _notes(datetime(2026, 11, 19, 20, 0)) == []


def test_aware_time_is_converted_to_lagos() -> None:
    minus5 = timezone(timedelta(hours=-5))
    plus5 = timezone(timedelta(hours=5))
    # Friday 10:00 at -05:00 is 16:00 in Lagos: note (naive 10:00 would give none).
    assert _notes(datetime(2026, 11, 20, 10, 0, tzinfo=minus5)) == [WEEKEND]
    # Saturday 02:00 at +05:00 is Friday 22:00 in Lagos: note.
    assert _notes(datetime(2026, 11, 21, 2, 0, tzinfo=plus5)) == [WEEKEND]
    # Sunday 23:30 at -05:00 is Monday 05:30 in Lagos: no note.
    assert _notes(datetime(2026, 11, 22, 23, 30, tzinfo=minus5)) == []


def test_no_time_no_note() -> None:
    assert _notes(None) == []


def test_amount_just_below_and_at_threshold() -> None:
    assert risk_notes(make_parsed(amount_kobo=49_999_999)) == []
    assert risk_notes(make_parsed(amount_kobo=50_000_000)) == [LARGE]


def test_custom_threshold_and_bad_threshold() -> None:
    assert risk_notes(make_parsed(amount_kobo=100), large_amount_kobo=100) == [LARGE]
    assert risk_notes(make_parsed(amount_kobo=100), large_amount_kobo=101) == []
    # A float or a bool falls back to the default 50000000.
    assert risk_notes(make_parsed(amount_kobo=100), large_amount_kobo=1.0) == []  # type: ignore[arg-type]
    assert risk_notes(make_parsed(amount_kobo=100), large_amount_kobo=True) == []  # type: ignore[arg-type]


def test_bool_amount_is_not_an_amount() -> None:
    assert risk_notes(make_parsed(amount_kobo=True), large_amount_kobo=1) == []  # type: ignore[arg-type]


def test_collection_text_curly_quotes_and_mixed_case() -> None:
    text = "Please, the \u201cDRIVER\u201d is here, it\u2019s urgent"
    assert risk_notes(make_parsed(), alert_text=text) == [COLLECT]
    assert risk_notes(make_parsed(), alert_text="PICK   UP\tNOW!") == [COLLECT]
    assert risk_notes(make_parsed(), alert_text="Pickup now") == [COLLECT]


def test_collection_words_must_be_whole_words() -> None:
    assert risk_notes(make_parsed(), alert_text="drivers and riderless") == []
    assert risk_notes(make_parsed(), alert_text=None) == []
    assert risk_notes(make_parsed(), alert_text=123) == []  # type: ignore[arg-type]


def test_all_three_in_order() -> None:
    parsed = make_parsed(alert_time=FRIDAY.replace(hour=15), amount_kobo=50_000_000)
    assert risk_notes(parsed, alert_text="rider outside") == [WEEKEND, LARGE, COLLECT]
