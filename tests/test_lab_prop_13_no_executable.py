"""Property 13: no executable, unescaped or reflected content in Lab output."""

from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import InMemoryCheckStore, SlidingWindowLimiter
from ghost_credit.lab_router import route
from lab_fakes import FIXED_NOW, FakeRunCheck, make_result

_payloads = st.sampled_from(
    [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "\"><svg onload=alert(1)>",
        "</script><script>alert(2)</script>",
    ]
)
_noise = st.text(alphabet="abc <>&\"'/", max_size=20)
_attack = st.builds(lambda a, p, b: a + p + b, _noise, _payloads, _noise)


# Feature: the-lab, Property 13: No executable, unescaped or reflected content ever appears in Lab HTML
# **Validates: Requirements 7.4, 8.1, 8.4**
@settings(max_examples=100, deadline=None)
@given(_attack, _attack)
def test_attack_text_is_never_reflected_or_executable(submitted, field):
    store = InMemoryCheckStore()
    store.save(
        {"check_id": "c1", "checked_at": "2026-11-20T10:02:11+01:00", "channel": "lab",
         "verdict": "SUSPICIOUS", "owner_label": "SUSPICIOUS", "amount_kobo": 1,
         "claimed_bank": field, "red_flags": [], "reasons": [field],
         "risk_notes": [field], "expires_at": 1}
    )
    fake = FakeRunCheck(make_result(reasons=[field], notes=[field], bank=field, reply=field))
    common = dict(now=FIXED_NOW, store=store, limiter=SlidingWindowLimiter(), run_check_fn=fake)

    page_status, page_headers, page = route("GET", "/lab", {"q": submitted}, {"x": submitted}, b"", **common)
    check = route("POST", "/lab/check", None, {}, json.dumps({"text": submitted}).encode(), **common)
    data = route("GET", "/lab/data", None, {}, b"", **common)
    page_after = route("GET", "/lab", None, {}, b"", **common)[2]

    assert page_status == 200 and "html" in page_headers["Content-Type"]
    # The submitted text and record fields never appear in the HTML page.
    for html_text in (page, page_after):
        assert submitted not in html_text and field not in html_text
        assert html_text.count("<script") == 1
        assert "onerror=" not in html_text
    # JSON bodies carry no raw angle brackets, so they can never read as markup.
    for _, _, body in (check, data):
        assert "<" not in body and ">" not in body
    assert json.loads(check[2])["reply"] == field
