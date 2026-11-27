"""Property 8: record_check never raises and never changes the reply."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import record_check
from lab_fakes import RaisingStore, check_results, nows

_errors = st.sampled_from(
    [RuntimeError("boom"), ValueError("bad"), KeyError("k"), OSError("disk"), TypeError("t")]
)


# Feature: the-lab, Property 8: Record_Check never raises and never changes the reply
# **Validates: Requirements 3.10, 3.11, 3.12**
@settings(max_examples=100, deadline=None)
@given(check_results, st.text(max_size=10), nows, st.one_of(st.none(), _errors))
def test_never_raises_and_reply_unchanged(result, channel, now, error):
    reply_before = result.reply
    store = None if error is None else RaisingStore(error)
    assert record_check(store, result, channel, now) is None
    assert result.reply is reply_before


@settings(max_examples=100, deadline=None)
@given(st.one_of(st.none(), st.integers(), st.text(max_size=5)), nows)
def test_junk_result_never_raises(junk, now):
    store = RaisingStore(RuntimeError("never reached"))
    assert record_check(store, junk, "lab", now) is None
