"""Tests for the DynamoDB used-reference ledger. Fakes only: no AWS, no boto3."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from deploy_helpers import load_deploy_module
from ghost_credit import ledger
from ghost_credit.ledger import (
    DynamoUsedReferences,
    LedgerError,
    get_used_references,
    hash_reference,
)
from ghost_credit.pipeline import InMemoryUsedReferences

ROOT = Path(__file__).resolve().parent.parent
# Fake key built from pieces so it never looks like a real secret.
KEY = "fake-" + "ledger-" + "key-" + "r5t8"
ENV = {"LEDGER_HMAC_KEY": KEY}
NOW = 1_800_000_000.0


class AwsError(Exception):
    """A fake AWS error that carries a response code."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.response = {"Error": {"Code": code}}


class FakeDynamo:
    """Records calls. ``item`` is what get_item finds; ``error`` is raised."""

    def __init__(self, item: dict | None = None, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.item = item
        self.error = error

    def get_item(self, **kwargs):
        self.calls.append(("get_item", kwargs))
        if self.error:
            raise self.error
        return {"Item": self.item} if self.item else {}

    def put_item(self, **kwargs):
        self.calls.append(("put_item", kwargs))
        if self.error:
            raise self.error
        return {}


def make(client: FakeDynamo, env: dict | None = None) -> DynamoUsedReferences:
    return DynamoUsedReferences(client=client, env=ENV if env is None else env,
                                clock=lambda: NOW)


# Prefixes keep a reference from matching inside hex digits by accident.
references = st.text(min_size=4, max_size=60).map(lambda s: "REF_" + s)
keys = st.text(alphabet="abcdefghijklmnop", min_size=4, max_size=20).map(lambda s: "KEY_" + s)


def _strings(item: dict) -> list[str]:
    return [json.dumps(item)] + [str(v) for v in item.values()]


# Feature: used-ref ledger, Property A: nothing raw is stored
# **Validates: stored item holds only ref_hash and expires_at**
@settings(max_examples=100, deadline=None)
@given(references, keys)
def test_item_has_no_raw_reference_or_key(reference: str, key: str) -> None:
    client = FakeDynamo()
    make(client, {"LEDGER_HMAC_KEY": key}).mark_used(reference)
    item = client.calls[0][1]["Item"]
    assert set(item) == {"ref_hash", "expires_at"}
    blob = json.dumps(item, ensure_ascii=True)
    assert json.dumps(reference)[1:-1] not in blob and reference not in blob
    assert key not in blob


# Property B: stable, distinct, well-formed hashes
# **Validates: ref_hash is "hmac:" + 64 lowercase hex**
@settings(max_examples=100, deadline=None)
@given(references, references, keys, keys)
def test_hash_is_stable_distinct_and_well_formed(r1, r2, k1, k2) -> None:
    first = hash_reference(r1, k1)
    assert first == hash_reference(r1, k1)
    assert re.fullmatch(r"hmac:[0-9a-f]{64}", first)
    if r1 != r2:
        assert first != hash_reference(r2, k1)
    if k1 != k2:
        assert first != hash_reference(r1, k2)


# Property C: errors never escape mark_used or leak the reference
# **Validates: failure behaviour equals today's**
@settings(max_examples=60, deadline=None)
@given(references)
def test_errors_do_not_leak_or_escape(reference: str) -> None:
    records: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    handler = Capture()
    logger = logging.getLogger("ghost_credit.ledger")
    logger.addHandler(handler)
    try:
        client = FakeDynamo(error=AwsError("Boom", "failed for " + reference + KEY))
        ledger_under_test = make(client)
        ledger_under_test.mark_used(reference)  # must not raise
        with pytest.raises(LedgerError) as caught:
            ledger_under_test.is_used(reference)
    finally:
        logger.removeHandler(handler)
    assert reference not in str(caught.value) and KEY not in str(caught.value)
    assert all(reference not in line and KEY not in line for line in records)


# Property D: 30-day expiry
# **Validates: expires_at is checked time + 2,592,000**
@settings(max_examples=100, deadline=None)
@given(st.integers(min_value=0, max_value=4_000_000_000))
def test_expires_at_is_checked_time_plus_30_days(now: int) -> None:
    client = FakeDynamo()
    DynamoUsedReferences(client=client, env=ENV, clock=lambda: float(now)).mark_used("REF_x1")
    assert client.calls[0][1]["Item"]["expires_at"] == {"N": str(now + 2_592_000)}


# --- Examples ---------------------------------------------------------------


def test_mark_used_is_one_conditional_put_on_the_default_table() -> None:
    client = FakeDynamo()
    make(client).mark_used("REF_abc1")
    assert [name for name, _ in client.calls] == ["put_item"]
    sent = client.calls[0][1]
    assert sent["TableName"] == "ghost-credit-used-refs"
    assert sent["ConditionExpression"] == "attribute_not_exists(ref_hash)"


def test_table_name_comes_from_the_environment() -> None:
    client = FakeDynamo()
    make(client, {**ENV, "USED_REFS_TABLE": "other-table"}).mark_used("REF_abc1")
    assert client.calls[0][1]["TableName"] == "other-table"


def test_conditional_check_failed_counts_as_success(caplog) -> None:
    client = FakeDynamo(error=AwsError("ConditionalCheckFailedException"))
    with caplog.at_level(logging.WARNING, logger="ghost_credit.ledger"):
        make(client).mark_used("REF_abc1")
    assert caplog.text == ""


def test_is_used_hit_and_miss_use_a_consistent_read() -> None:
    hit = FakeDynamo(item={"ref_hash": {"S": "x"}})
    assert make(hit).is_used("REF_abc1") is True
    sent = hit.calls[0][1]
    assert sent["ConsistentRead"] is True
    assert sent["Key"]["ref_hash"]["S"] == hash_reference("REF_abc1", KEY)
    assert make(FakeDynamo()).is_used("REF_abc1") is False


def test_missing_key_or_empty_reference_raises_for_is_used() -> None:
    client = FakeDynamo()
    with pytest.raises(LedgerError):
        make(client, {}).is_used("REF_abc1")
    with pytest.raises(LedgerError):
        make(client).is_used("")
    assert client.calls == []


def test_key_is_read_at_call_time() -> None:
    env: dict = {}
    client = FakeDynamo()
    ledger_under_test = make(client, env)
    env["LEDGER_HMAC_KEY"] = KEY
    ledger_under_test.mark_used("REF_abc1")
    assert client.calls[0][1]["Item"]["ref_hash"]["S"] == hash_reference("REF_abc1", KEY)


def test_factory_picks_dynamo_only_when_the_key_is_set() -> None:
    assert isinstance(get_used_references(env=ENV, client=FakeDynamo()), DynamoUsedReferences)
    for env in ({}, {"LEDGER_HMAC_KEY": ""}, {"LEDGER_HMAC_KEY": "  "}):
        found = get_used_references(env=env)
        assert isinstance(found, InMemoryUsedReferences)
        assert found is get_used_references(env=env)


def test_module_imports_with_boto3_blocked() -> None:
    code = (
        "import sys\n"
        "class B:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in ('boto3', 'botocore'):\n"
        "            raise ImportError('blocked')\n"
        "sys.meta_path.insert(0, B())\n"
        "import ghost_credit.ledger\n"
        "assert 'boto3' not in sys.modules\n"
    )
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    done = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True)
    assert done.returncode == 0, done.stderr.decode()[-300:]


def test_whatsapp_default_ledger_is_dynamo_only_with_the_key(monkeypatch) -> None:
    from whatsapp_fakes import FakeCheck, fake_env, post, text_message, to_bytes, wrap_messages

    body = to_bytes(wrap_messages([text_message("hello")]))
    for overrides, expected in (({"LEDGER_HMAC_KEY": KEY}, DynamoUsedReferences),
                                ({"LEDGER_HMAC_KEY": None}, InMemoryUsedReferences)):
        check = FakeCheck()
        with fake_env(**overrides):
            from whatsapp_fakes import RecordingSend
            post(body, check=check, send=RecordingSend())
        assert isinstance(check.kwargs[0]["used_references"], expected)


def test_whatsapp_injected_ledger_is_used_for_paystack_is_used() -> None:
    from whatsapp_fakes import FakeCheck, RecordingSend, fake_env, post, text_message, to_bytes, wrap_messages

    injected = InMemoryUsedReferences()
    check = FakeCheck()
    with fake_env():
        post(to_bytes(wrap_messages([text_message("hello")])), check=check,
             send=RecordingSend(), used_references=injected)
    assert check.kwargs[0]["used_references"] is injected


def test_lab_route_does_not_use_the_ledger() -> None:
    from datetime import datetime, timedelta, timezone

    from ghost_credit.lab_router import route
    from ghost_credit.lab import SlidingWindowLimiter

    seen: list[dict] = []

    def fake_run(text, a, b, c, now, **kwargs):
        seen.append(kwargs)
        raise RuntimeError("stop here")

    now = datetime(2026, 11, 20, 10, 0, tzinfo=timezone(timedelta(hours=1)))
    route("POST", "/lab/check", None, {}, json.dumps({"text": "hi"}).encode(),
          now=now, store=None, limiter=SlidingWindowLimiter(), run_check_fn=fake_run)
    assert seen and "used_references" not in seen[0]


def test_deploy_policy_has_used_refs_statement_with_exactly_get_and_put() -> None:
    deploy = load_deploy_module()
    statements = deploy.permissions_policy("111122223333")["Statement"]
    used = [s for s in statements if "ghost-credit-used-refs" in str(s["Resource"])]
    assert len(used) == 1
    assert sorted(used[0]["Action"]) == ["dynamodb:GetItem", "dynamodb:PutItem"]
    assert used[0]["Resource"] == (
        "arn:aws:dynamodb:us-east-1:111122223333:table/ghost-credit-used-refs"
    )
    assert "LEDGER_HMAC_KEY" in deploy.LAMBDA_VARIABLE_NAMES
    assert ledger.DEFAULT_USED_REFS_TABLE == deploy.USED_REFS_TABLE_NAME
