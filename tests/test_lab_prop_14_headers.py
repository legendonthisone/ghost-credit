"""Property 14: every Lab response carries the required security headers."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import SlidingWindowLimiter
from ghost_credit.lab_router import route
from lab_fakes import FIXED_NOW, FakeRunCheck

CSP = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'"

_paths = st.one_of(
    st.sampled_from(["/lab", "/lab/", "/lab/data", "/lab/check", "/lab/nope", "/lab/check/x"]),
    st.text(max_size=20).map(lambda s: "/lab" + s),
    st.one_of(st.none(), st.integers(), st.text(max_size=10)),
)
_methods = st.one_of(
    st.sampled_from(["GET", "POST", "PUT", "get", "post", "HEAD", ""]), st.none(), st.integers()
)
_bodies = st.one_of(
    st.none(), st.binary(max_size=200), st.text(max_size=50),
    st.just(b'{"text": 5}'), st.just(b'{"text": "hi"}'), st.just(b"[]"),
)
_junk = st.one_of(st.none(), st.integers(), st.text(max_size=10),
                  st.dictionaries(st.text(max_size=5), st.text(max_size=5), max_size=3))


# Feature: the-lab, Property 14: Every Lab response carries the required security headers
# **Validates: Requirements 8.3**
@settings(max_examples=100, deadline=None)
@given(_methods, _paths, _junk, _junk, _bodies, st.booleans())
def test_every_response_has_security_headers(method, path, query, headers, body, check_raises):
    status, out_headers, out_body = route(
        method, path, query, headers, body, now=FIXED_NOW, store=None,
        limiter=SlidingWindowLimiter(), run_check_fn=FakeRunCheck(raises=check_raises),
    )
    assert isinstance(status, int) and isinstance(out_body, str)
    assert out_headers["Content-Security-Policy"] == CSP
    assert out_headers["X-Content-Type-Options"] == "nosniff"
    assert out_headers["Cache-Control"] == "no-store"
