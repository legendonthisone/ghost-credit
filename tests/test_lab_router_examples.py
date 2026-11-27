"""Example tests for the Lab router and the sample file."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ghost_credit.lab import (
    ALLOWED_FIELDS,
    SlidingWindowLimiter,
    sanitise_record,
)
from ghost_credit.lab_router import SAMPLE_PATH, route
from lab_fakes import FIXED_NOW, FakeRunCheck, SpyStore


def _call(method, path, body=b"", **kw):
    kw.setdefault("store", None)
    kw.setdefault("limiter", SlidingWindowLimiter())
    return route(method, path, None, {}, body, now=FIXED_NOW, **kw)


def _check_body(text):
    return json.dumps({"text": text}).encode("utf-8")


def _sample():
    return json.loads(Path(SAMPLE_PATH).read_text(encoding="utf-8"))


def test_page_is_served():
    status, headers, body = _call("GET", "/lab")
    assert status == 200 and headers["Content-Type"].startswith("text/html")
    assert "<!DOCTYPE html>" in body


def test_unknown_path_404_and_wrong_method_405():
    assert _call("GET", "/lab/other")[0] == 404
    assert _call("POST", "/lab")[0] == 405
    assert _call("GET", "/lab/check")[0] == 405


def test_bad_json_is_400_and_no_check():
    fake = FakeRunCheck()
    assert _call("POST", "/lab/check", b"not json", run_check_fn=fake)[0] == 400
    assert _call("POST", "/lab/check", b'{"text": 5}', run_check_fn=fake)[0] == 400
    assert fake.calls == []


def test_2000_chars_ok_and_2001_rejected():
    fake = FakeRunCheck()
    assert _call("POST", "/lab/check", _check_body("a" * 2000), run_check_fn=fake)[0] == 200
    assert _call("POST", "/lab/check", _check_body("a" * 2001), run_check_fn=fake)[0] == 413
    assert len(fake.calls) == 1


def test_21st_call_in_one_minute_returns_429():
    fake = FakeRunCheck()
    limiter = SlidingWindowLimiter()
    codes = [
        _call("POST", "/lab/check", _check_body("hi"), limiter=limiter, run_check_fn=fake)[0]
        for _ in range(21)
    ]
    assert codes == [200] * 20 + [429]
    assert len(fake.calls) == 20


def test_check_logs_once_with_channel_lab():
    store = SpyStore()
    _call("POST", "/lab/check", _check_body("hi"), store=store, run_check_fn=FakeRunCheck())
    assert len(store.saved) == 1 and store.saved[0]["channel"] == "lab"


def test_failing_check_gives_safe_fallback_with_headers():
    status, headers, body = _call(
        "POST", "/lab/check", _check_body("hi"), run_check_fn=FakeRunCheck(raises=True)
    )
    assert status == 404 and "Traceback" not in body
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_real_pipeline_check_without_paystack_key(monkeypatch):
    monkeypatch.delenv("PAYSTACK_SECRET_KEY", raising=False)
    sms = ("GTBank Credit Alert: Acct 012****789 credited NGN 45,000.00 from AMAKA "
           "on 20-Nov-2026 10:02. Avail Bal: NGN 120,000.00")
    store = SpyStore()
    status, _, body = _call("POST", "/lab/check", _check_body(sms), store=store)
    data = json.loads(body)
    assert status == 200 and data["verdict"] in ("UNVERIFIED", "SUSPICIOUS")
    assert data["amount_kobo"] == 4500000
    assert "AMAKA" not in json.dumps(store.saved)


def test_data_sample_equals_file_with_required_mix():
    status, _, body = _call("GET", "/lab/data")
    data = json.loads(body)
    sample = _sample()
    assert status == 200 and data["sample"] == sample and len(sample) == 6
    labels = sorted(r["owner_label"] for r in sample)
    assert labels == sorted(["ALIVE", "GHOST", "GHOST", "SUSPICIOUS", "UNVERIFIED", "SUSPICIOUS"])
    ghosts = [r for r in sample if r["owner_label"] == "GHOST"]
    texts = [" ".join(r["reasons"]).lower() for r in ghosts]
    assert any("no matching payment" in t for t in texts)
    assert any("already used" in t for t in texts)
    assert any("TRANSFER_REQUEST_WORDING" in r["red_flags"] for r in sample)


def test_sample_file_has_only_allowed_fields_and_no_digit_runs():
    for record in _sample():
        assert set(record) == set(ALLOWED_FIELDS)
        masked = sanitise_record(record)
        for name in ALLOWED_FIELDS:
            if name not in ("check_id", "checked_at"):
                assert masked[name] == record[name], name
        assert not re.search(r"\d(?:[ \-.,]*\d){6,}", record["check_id"])
