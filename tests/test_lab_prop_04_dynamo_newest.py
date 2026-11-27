"""Property 4: DynamoCheckStore.newest sorts and limits a Scan."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.lab import DynamoCheckStore
from lab_fakes import FakeDynamoClient, valid_records


def _typed(record: dict) -> dict:
    """Encode a record the way DynamoDB returns it (independent of the code under test)."""
    item = {}
    for name, value in record.items():
        if value is None:
            item[name] = {"NULL": True}
        elif isinstance(value, int):
            item[name] = {"N": str(value)}
        elif isinstance(value, list):
            item[name] = {"L": [{"S": v} for v in value]}
        else:
            item[name] = {"S": value}
    return item


# Feature: the-lab, Property 4: DynamoCheckStore.newest sorts and limits a Scan
# **Validates: Requirements 2.6**
@settings(max_examples=100, deadline=None)
@given(
    st.lists(valid_records, max_size=70),
    st.integers(min_value=0, max_value=80),
)
def test_newest_sorts_desc_and_limits(records, limit):
    client = FakeDynamoClient([_typed(r) for r in records])
    got = DynamoCheckStore("t", client=client).newest(limit)
    assert len(client.scans) == 1 and not client.puts
    expected_times = sorted((r["checked_at"] for r in records), reverse=True)
    expected_times = expected_times[: min(limit, 50)]
    assert [r["checked_at"] for r in got] == expected_times
    assert len(got) <= 50
