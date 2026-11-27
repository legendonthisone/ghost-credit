"""Property 9: GET /lab/data returns both arrays, store records, allowed fields."""

from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import ALLOWED_FIELDS, InMemoryCheckStore, SlidingWindowLimiter
from ghost_credit.lab_router import route
from lab_fakes import FIXED_NOW, RaisingStore, valid_records


def _get_data(store):
    return route("GET", "/lab/data", None, {}, b"", now=FIXED_NOW, store=store,
                 limiter=SlidingWindowLimiter())


# Feature: the-lab, Property 9: GET /lab/data always returns both arrays, records from the store, within the allowed fields
# **Validates: Requirements 5.1, 5.2, 5.4**
@settings(max_examples=100, deadline=None)
@given(st.lists(valid_records, max_size=60))
def test_data_has_store_records_and_six_samples(records):
    store = InMemoryCheckStore()
    for record in records:
        store.save(record)
    status, _, body = _get_data(store)
    data = json.loads(body)
    assert status == 200
    assert data["records"] == store.newest(50)
    assert len(data["sample"]) == 6
    for record in data["records"]:
        assert set(record) <= set(ALLOWED_FIELDS)


@settings(max_examples=100, deadline=None)
@given(st.sampled_from(["none", "raises"]))
def test_no_store_or_failing_store_gives_empty_records(kind):
    store = None if kind == "none" else RaisingStore(RuntimeError("down"))
    status, _, body = _get_data(store)
    data = json.loads(body)
    assert status == 200 and data["records"] == [] and len(data["sample"]) == 6
