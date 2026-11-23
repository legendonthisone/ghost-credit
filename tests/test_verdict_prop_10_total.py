"""Feature: verdict-engine, Property 10: Decide is total and treats junk as defaults."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.parser import ParsedAlert
from ghost_credit.pattern_network import LookupResult
from ghost_credit.verdict import decide
from verdict_helpers import lookup_results, paystack_inputs, red_flag_lists

CODES = {"CONFIRMED", "NOT_FOUND", "SUSPICIOUS", "UNVERIFIED"}

_junk = st.one_of(st.none(), st.integers(), st.text(max_size=20), st.just(object()))


class _Raises:
    """An object whose every attribute read fails."""

    def __getattr__(self, name: str) -> object:
        raise RuntimeError("boom")


@settings(max_examples=200)
@given(parsed=st.one_of(_junk, st.builds(ParsedAlert, red_flags=red_flag_lists)),
       paystack=st.one_of(paystack_inputs, _junk),
       lookup=st.one_of(lookup_results, _junk))
def test_always_a_valid_verdict(parsed, paystack, lookup) -> None:
    """**Validates: Requirements 4.3, 8.5**"""
    v = decide(parsed, paystack, lookup)
    assert v.code in CODES
    assert v.decided_by == "rules"


@settings(max_examples=100)
@given(junk=_junk, flags=red_flag_lists, matched=st.booleans())
def test_junk_equals_defaults(junk, flags, matched) -> None:
    """**Validates: Requirements 4.4, 4.5, 4.6**"""
    parsed = ParsedAlert(red_flags=flags)
    # A junk Paystack input behaves like None.
    assert decide(parsed, junk, None) == decide(parsed, None, None)
    # A non-list red_flags behaves like an empty list.
    bad = ParsedAlert(red_flags=junk)  # type: ignore[arg-type]
    if not isinstance(junk, list):
        assert decide(bad, None, None) == decide(ParsedAlert(red_flags=[]), None, None)
    # A bad LookupResult is not a Network_Match.
    assert decide(parsed, None, junk) == decide(parsed, None, None)
    # Non-boolean fields are not a match.
    odd = LookupResult(network_available=1, matched=matched)  # type: ignore[arg-type]
    assert decide(parsed, None, odd) == decide(parsed, None, None)


def test_forced_internal_error_is_unverified() -> None:
    """**Validates: Requirements 4.8**"""
    v = decide(_Raises(), None, None)  # type: ignore[arg-type]
    assert v.code == "UNVERIFIED"
    assert v.decided_by == "rules"
    assert len(v.reasons) == 1
