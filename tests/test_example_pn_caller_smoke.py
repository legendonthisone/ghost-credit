"""Example and smoke tests: hook-off caller run, imports, exports, single implementation."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from ghost_credit import pattern_network as pn
from ghost_credit.pattern_network import (
    NoopPatternNetwork,
    PatternNetwork,
    Signals,
    Verdict,
    get_network,
    safe_lookup,
    safe_report,
)

from pn_env import hook_env

_ROOT = Path(__file__).resolve().parent.parent
_MODULE = _ROOT / "src" / "ghost_credit" / "pattern_network.py"
_CONTRACT = _ROOT / "docs" / "pattern-network-contract.md"


def _contract_hook_off() -> dict:
    """Read the hook-off JSON block from the contract."""
    section = _CONTRACT.read_text(encoding="utf-8").split(
        "## Example: what this repo returns (hook off)"
    )[1]
    return json.loads(re.search(r"```json\n(.*?)```", section, re.S).group(1))


def _signals() -> Signals:
    return Signals(check_id="c1", checked_at="2026-11-20T10:40:05+01:00", channel="sms", amount_kobo=4500000)


def test_hook_off_end_to_end_matches_contract() -> None:
    expected = _contract_hook_off()
    for switch in (None, "off"):
        with hook_env(switch=switch):
            net = get_network()
            lookup = safe_lookup(net, _signals())
            worker = safe_report(net, Verdict(code="NOT_FOUND", paystack_checked=True), _signals())
            worker.join(5)
            receipt = net.report_pattern(Verdict(code="NOT_FOUND", paystack_checked=True), _signals())
        assert lookup.to_dict() == expected["lookup_patterns"]
        assert receipt.to_dict() == expected["report_pattern"]


def test_confirmed_is_not_reported() -> None:
    assert safe_report(NoopPatternNetwork(), Verdict(code="CONFIRMED", paystack_checked=True), _signals()) is None


def test_module_imports_no_network_library() -> None:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    banned = {"socket", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp", "ssl", "ftplib", "smtplib", "websockets"}
    assert not imported & banned


def test_module_has_no_shield_or_meko_code() -> None:
    text = _MODULE.read_text(encoding="utf-8").lower()
    assert "import fake_alert" not in text
    assert "from fake_alert" not in text
    assert "meko" not in text


def test_exports_exist() -> None:
    for name in ("Verdict", "Signals", "Match", "LookupResult", "ReportReceipt", "PatternNetwork", "NoopPatternNetwork"):
        assert name in pn.__all__
        assert hasattr(pn, name)


def test_noop_is_the_only_implementation() -> None:
    """Only the module's own classes count; test stubs live in other files."""
    own = [
        c for c in PatternNetwork.__subclasses__() if c.__module__ == pn.__name__
    ]
    assert own == [NoopPatternNetwork]


def test_nothing_maps_a_lookup_to_confirmed() -> None:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    for fn in funcs:
        returns_lookup = fn.returns is not None and "Verdict" in ast.unparse(fn.returns)
        takes_lookup = any(a.annotation is not None and "LookupResult" in ast.unparse(a.annotation) for a in fn.args.args)
        assert not (returns_lookup and takes_lookup)
