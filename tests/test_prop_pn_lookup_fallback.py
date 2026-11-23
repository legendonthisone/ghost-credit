"""Property test: a failing, odd or slow lookup always falls back to 'not available'."""

from __future__ import annotations

import time

from hypothesis import given, settings, strategies as st

from ghost_credit import pattern_network as pn
from ghost_credit.pattern_network import LookupResult, PatternNetwork, safe_lookup

import pn_strategies as S


class _Stub(PatternNetwork):
    """A network that raises, returns a wrong type, or sleeps, as told."""

    def __init__(self, mode: str, value=None, delay: float = 0.0) -> None:
        self.mode, self.value, self.delay = mode, value, delay

    def lookup_patterns(self, signals):
        if self.delay:
            time.sleep(self.delay)
        if self.mode == "raise":
            raise self.value
        return self.value

    def report_pattern(self, verdict, signals):  # pragma: no cover - not used here
        raise NotImplementedError


def _assert_fallback(result) -> None:
    assert isinstance(result, LookupResult)
    assert result.network_available is False
    assert result.matched is False
    assert result.matches == []


_errors = st.sampled_from([ValueError("x"), RuntimeError("y"), KeyError("z"), OSError("o"), Exception("e")])
_wrong = st.sampled_from([None, 5, "text", {"matched": True}, [], object()])


@settings(max_examples=100)
@given(S.signals, _errors)
def test_raise_falls_back(signals, error) -> None:
    """Feature: pattern-network-hook, Property 15: Lookup falls back safely (raise).
    **Validates: Requirements 7.3**
    """
    _assert_fallback(safe_lookup(_Stub("raise", error), signals))


@settings(max_examples=100)
@given(S.signals, _wrong)
def test_wrong_type_falls_back(signals, value) -> None:
    """Feature: pattern-network-hook, Property 15: Lookup falls back safely (wrong type).
    **Validates: Requirements 7.4**
    """
    _assert_fallback(safe_lookup(_Stub("return", value), signals))


@settings(max_examples=5, deadline=None)
@given(S.signals, st.floats(min_value=0.2, max_value=0.6))
def test_slow_falls_back_within_limit(signals, extra) -> None:
    """Feature: pattern-network-hook, Property 15: Lookup falls back safely (slow).
    **Validates: Requirements 7.1, 7.2**
    """
    good = LookupResult(network_available=True, matched=True)
    start = time.monotonic()
    result = safe_lookup(_Stub("return", good, delay=pn.LOOKUP_TIMEOUT_SECONDS + extra), signals)
    elapsed = time.monotonic() - start
    _assert_fallback(result)
    assert elapsed < pn.LOOKUP_TIMEOUT_SECONDS + extra
    assert elapsed < pn.LOOKUP_TIMEOUT_SECONDS + 0.3
