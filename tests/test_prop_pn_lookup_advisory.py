"""Property test: lookup results pass through unchanged and logs hold no payload data."""

from __future__ import annotations

import copy

from hypothesis import given, settings, strategies as st

from ghost_credit.pattern_network import PatternNetwork, safe_lookup

import pn_strategies as S
from pn_env import FAKE_KEY, capture_logs


class _Fixed(PatternNetwork):
    """A network that returns a fixed result or raises a fixed error."""

    def __init__(self, result=None, error=None) -> None:
        self.result, self.error = result, error

    def lookup_patterns(self, signals):
        if self.error is not None:
            raise self.error
        return self.result

    def report_pattern(self, verdict, signals):  # pragma: no cover - not used here
        raise NotImplementedError


@settings(max_examples=100)
@given(S.signals, S.verdicts, S.lookup_results)
def test_result_unchanged_and_verdict_untouched(signals, verdict, stub_result) -> None:
    """Feature: pattern-network-hook, Property 16: Lookup is advisory (pass-through).
    **Validates: Requirements 7.6**
    """
    before = copy.deepcopy(verdict)
    result = safe_lookup(_Fixed(result=stub_result), signals)
    assert result is stub_result
    assert verdict == before


_marker = st.text(alphabet="QXZJ", min_size=8, max_size=12)


@settings(max_examples=100)
@given(_marker, _marker, _marker)
def test_failure_logs_hold_no_payload(ref_marker, hash_marker, secret_marker) -> None:
    """Feature: pattern-network-hook, Property 16: Lookup logs no payload data.
    **Validates: Requirements 3.8, 7.5**
    """
    signals = S.Signals(
        check_id="c1",
        checked_at="2026-11-20T10:40:05+01:00",
        channel="sms",
        amount_kobo=100,
        claimed_reference=ref_marker,
        payer_name_hash="hmac:" + hash_marker,
    )
    error = RuntimeError(f"{ref_marker} {hash_marker} {secret_marker} {FAKE_KEY}")
    with capture_logs() as lines:
        safe_lookup(_Fixed(error=error), signals)
    assert lines, "the failure should be logged"
    text = "\n".join(lines)
    for secret in (ref_marker, hash_marker, secret_marker, FAKE_KEY, "c1"):
        assert secret not in text
