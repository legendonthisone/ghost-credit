"""Property 2: InMemoryCheckStore round-trips saved records."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import InMemoryCheckStore
from lab_fakes import valid_records


# Feature: the-lab, Property 2: InMemoryCheckStore round-trips saved records
# **Validates: Requirements 2.2**
@settings(max_examples=100, deadline=None)
@given(st.lists(valid_records, max_size=30), st.integers(min_value=0, max_value=40))
def test_newest_returns_saved_records_latest_first(records, limit):
    store = InMemoryCheckStore()
    for record in records:
        store.save(record)
    got = store.newest(limit)
    assert got == records[::-1][:limit]
    assert len(got) <= limit
