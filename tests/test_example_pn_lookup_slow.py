"""Example test: a lookup slower than 1.5 seconds gives network_available false."""

from __future__ import annotations

import time

from ghost_credit.pattern_network import (
    LookupResult,
    PatternNetwork,
    Signals,
    safe_lookup,
)


class _Slow(PatternNetwork):
    """A network that answers after 2 seconds."""

    def lookup_patterns(self, signals):
        time.sleep(2.0)
        return LookupResult(network_available=True, matched=True)

    def report_pattern(self, verdict, signals):  # pragma: no cover - not used here
        raise NotImplementedError


def test_slow_lookup_gives_not_available() -> None:
    signals = Signals(check_id="c1", checked_at="2026-11-20T10:40:05+01:00", channel="sms", amount_kobo=100)
    start = time.monotonic()
    result = safe_lookup(_Slow(), signals)
    elapsed = time.monotonic() - start
    assert result.network_available is False
    assert result.matched is False
    assert result.matches == []
    assert 1.4 <= elapsed < 1.9
