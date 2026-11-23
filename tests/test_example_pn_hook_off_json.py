"""Example tests: the Noop answers match the contract's hook-off JSON and field tables."""

from __future__ import annotations

import json
import re
from dataclasses import fields
from pathlib import Path

from ghost_credit.pattern_network import (
    LookupResult,
    Match,
    NoopPatternNetwork,
    ReportReceipt,
    Signals,
    Verdict,
)

_CONTRACT = Path(__file__).resolve().parent.parent / "docs" / "pattern-network-contract.md"


def _contract_hook_off() -> dict:
    """Read the 'what this repo returns (hook off)' JSON block from the contract."""
    text = _CONTRACT.read_text(encoding="utf-8")
    section = text.split("## Example: what this repo returns (hook off)")[1]
    block = re.search(r"```json\n(.*?)```", section, re.S).group(1)
    return json.loads(block)


def _table_fields(heading: str) -> set:
    """Read the first-column field names of a contract table under a '## heading'."""
    text = _CONTRACT.read_text(encoding="utf-8")
    section = text.split("## " + heading + "\n")[1].split("\n## ")[0]
    names = set()
    for line in section.splitlines():
        m = re.match(r"\|\s*([a-z_]+)\s*\|", line)
        if m and m.group(1) != "field":
            names.add(m.group(1))
    return names


def test_noop_matches_contract_json() -> None:
    expected = _contract_hook_off()
    net = NoopPatternNetwork()
    signals = Signals(check_id="c", checked_at="2026-11-20T10:40:05+01:00", channel="sms", amount_kobo=4500000)
    verdict = Verdict(code="NOT_FOUND", paystack_checked=True)
    assert net.lookup_patterns(signals).to_dict() == expected["lookup_patterns"]
    assert net.report_pattern(verdict, signals).to_dict() == expected["report_pattern"]


def test_field_names_match_contract_tables() -> None:
    assert {f.name for f in fields(Signals)} == _table_fields("signals")
    assert {f.name for f in fields(Verdict)} == _table_fields("verdict")
    assert len(fields(Signals)) == 16
    assert len(fields(Verdict)) == 5
    assert {f.name for f in fields(LookupResult)} == {
        "schema_version", "network_available", "matched", "matches", "trace_url",
    }
    assert {f.name for f in fields(ReportReceipt)} == {
        "schema_version", "accepted", "status", "pattern_id", "trace_url",
    }
    assert {f.name for f in fields(Match)} == {
        "pattern_id", "matched_on", "first_seen", "times_seen",
        "shops_seen", "last_verdict", "confidence", "summary",
    }


def test_defaults() -> None:
    signals = Signals(check_id="c", checked_at="t", channel="sms", amount_kobo=1)
    assert signals.schema_version == "1.0"
    assert LookupResult(network_available=False, matched=False).schema_version == "1.0"
    assert ReportReceipt(accepted=False, status="disabled").schema_version == "1.0"
    assert Verdict(code="UNVERIFIED", paystack_checked=False).decided_by == "rules"
