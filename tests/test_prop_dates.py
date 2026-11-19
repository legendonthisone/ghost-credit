from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import parse_sms_alert

MONTH_ABBRS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FORMATS = ["slash", "dash", "dash_mon", "space_mon", "iso"]


def _write(fmt: str, year: int, month: int, day: int, hour: int, minute: int,
           second: int | None, month_abbr: str | None = None) -> str:
    """Write a date and time in a Recognised_Date_Format. Fields are used as given."""
    time_part = f"{hour:02d}:{minute:02d}" + ("" if second is None else f":{second:02d}")
    mon = month_abbr if month_abbr is not None else (MONTH_ABBRS[month - 1] if 1 <= month <= 12 else "")
    date_part = {
        "slash": f"{day:02d}/{month:02d}/{year:04d}",
        "dash": f"{day:02d}-{month:02d}-{year:04d}",
        "dash_mon": f"{day:02d}-{mon}-{year:04d}",
        "space_mon": f"{day:02d} {mon} {year:04d}",
        "iso": f"{year:04d}-{month:02d}-{day:02d}",
    }[fmt]
    return f"{date_part} {time_part}"


def _alert(written: str) -> str:
    return f"Credit Alert! Amt: N5,000.00 Acct: 012****789 Date: {written} Bal: N120,500.00"


@st.composite
def valid_datetime(draw):
    fmt = draw(st.sampled_from(FORMATS))
    dt = draw(st.datetimes(min_value=datetime(1900, 1, 1), max_value=datetime(2100, 12, 31, 23, 59, 59)))
    with_seconds = draw(st.booleans())
    return fmt, dt, with_seconds


@st.composite
def invalid_datetime(draw):
    """A date in a recognised layout with exactly one impossible component."""
    fmt = draw(st.sampled_from(FORMATS))
    base = draw(st.datetimes(min_value=datetime(1900, 1, 1), max_value=datetime(2100, 12, 31, 23, 59, 59)))
    year, month, day, hour, minute, second = base.year, base.month, base.day, base.hour, base.minute, base.second
    with_seconds = draw(st.booleans())
    kinds = ["day", "hour", "minute", "feb30", "feb29"]
    if with_seconds:
        kinds.append("second")
    if fmt in ("slash", "dash", "iso"):
        kinds.append("month")
    kind = draw(st.sampled_from(kinds))
    if kind == "month":
        month = draw(st.sampled_from([0] + list(range(13, 100))))
    elif kind == "day":
        day = draw(st.sampled_from([0] + list(range(32, 100))))
    elif kind == "hour":
        hour = draw(st.integers(24, 99))
    elif kind == "minute":
        minute = draw(st.integers(60, 99))
    elif kind == "second":
        second = draw(st.integers(60, 99))
    elif kind == "feb30":
        month, day = 2, draw(st.integers(30, 31))
    else:  # 29 February in a non-leap year
        non_leap = [y for y in range(1900, 2101) if not (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))]
        year, month, day = draw(st.sampled_from(non_leap)), 2, 29
    written = _write(fmt, year, month, day, hour, minute, second if with_seconds else None)
    return written


# Feature: alert-parser, Property 6: Valid and invalid dates
# **Validates: Requirements 3.3, 7.1, 7.3, 7.5, 7.6, 10.9**
@settings(max_examples=200)
@given(data=valid_datetime())
def test_valid_dates_parse(data):
    fmt, dt, with_seconds = data
    written = _write(fmt, dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second if with_seconds else None)
    result = parse_sms_alert(_alert(written), "TESTBANK")
    dt = dt.replace(microsecond=0)
    expected = dt if with_seconds else dt.replace(second=0)
    assert result.alert_time == expected, written
    assert result.alert_time.tzinfo is None, written
    assert "DATE_ODD" not in result.red_flags, written


# Feature: alert-parser, Property 6: Valid and invalid dates
# **Validates: Requirements 3.3, 7.1, 7.3, 7.5, 7.6, 10.9**
@settings(max_examples=200)
@given(written=invalid_datetime())
def test_impossible_dates_flagged(written):
    result = parse_sms_alert(_alert(written), "TESTBANK")
    assert result.alert_time is None, written
    assert result.red_flags.count("DATE_ODD") == 1, written
