"""Property 3: DynamoCheckStore.save sends exactly one well-shaped PutItem."""

from __future__ import annotations

from hypothesis import given, settings

from ghost_credit.lab import DynamoCheckStore
from lab_fakes import FakeDynamoClient, valid_records


# Feature: the-lab, Property 3: DynamoCheckStore.save sends exactly one well-shaped PutItem
# **Validates: Requirements 2.5**
@settings(max_examples=100, deadline=None)
@given(valid_records)
def test_save_is_one_typed_put_item(record):
    client = FakeDynamoClient()
    DynamoCheckStore("table-x", client=client).save(record)
    assert len(client.puts) == 1 and not client.scans
    call = client.puts[0]
    assert call["TableName"] == "table-x"
    item = call["Item"]
    assert set(item) == set(record)
    for name in ("check_id", "checked_at", "channel", "verdict", "owner_label"):
        assert item[name] == {"S": record[name]}
    assert item["expires_at"] == {"N": str(record["expires_at"])}
    if record["amount_kobo"] is None:
        assert item["amount_kobo"] == {"NULL": True}
    else:
        assert item["amount_kobo"] == {"N": str(record["amount_kobo"])}
    if record["claimed_bank"] is None:
        assert item["claimed_bank"] == {"NULL": True}
    else:
        assert item["claimed_bank"] == {"S": record["claimed_bank"]}
    for name in ("red_flags", "reasons", "risk_notes"):
        assert item[name] == {"L": [{"S": v} for v in record[name]]}
