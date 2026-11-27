"""Property 5: record_check builds a complete, correctly derived record."""

from __future__ import annotations

from datetime import datetime

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import ALLOWED_FIELDS, TTL_SECONDS, record_check
from ghost_credit.verdict import OWNER_LABELS
from lab_fakes import SpyStore, check_results, nows


# Feature: the-lab, Property 5: Record_Check builds a complete, correctly derived Check_Record
# **Validates: Requirements 3.3, 3.4**
@settings(max_examples=100, deadline=None)
@given(check_results, st.text(min_size=1, max_size=12), nows)
def test_record_is_complete_and_derived(result, channel, now):
    store = SpyStore()
    record_check(store, result, channel, now)
    assert len(store.saved) == 1
    saved = store.saved[0]
    assert set(saved) == set(ALLOWED_FIELDS)
    assert saved["verdict"] == result.verdict.code
    assert saved["owner_label"] == OWNER_LABELS[result.verdict.code]
    assert saved["amount_kobo"] == result.parsed.amount_kobo
    assert saved["checked_at"].endswith("+01:00")
    epoch = int(datetime.fromisoformat(saved["checked_at"]).timestamp())
    assert saved["expires_at"] == epoch + TTL_SECONDS == epoch + 2_592_000


@settings(max_examples=100, deadline=None)
@given(check_results, st.sampled_from(["whatsapp", "lab"]), nows)
def test_channel_is_kept(result, channel, now):
    store = SpyStore()
    record_check(store, result, channel, now)
    assert store.saved[0]["channel"] == channel
