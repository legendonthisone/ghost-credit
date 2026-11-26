"""Feature: whatsapp-webhook, Property 15: The printed plan and errors hold no values."""

from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

from deploy_helpers import load_deploy_module

deploy = load_deploy_module()

KEY_PREFIX = "sk_" + "test_"
secret_values = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=14, max_size=24
).map(lambda s: "zz-fake-" + s)


def _no_aws(*args, **kwargs):
    raise AssertionError("AWS must not be called")


def _run(lines: list[str], extra: list[str]) -> tuple[int, str]:
    """Run main with a temporary env file and return (exit code, printed text)."""
    out = io.StringIO()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "fake.env"
        path.write_text("\n".join(lines), encoding="utf-8")
        original = deploy._deploy
        deploy._deploy = _no_aws
        try:
            with contextlib.redirect_stdout(out):
                code = deploy.main(["--env-file", str(path), *extra])
        finally:
            deploy._deploy = original
    return code, out.getvalue()


@settings(max_examples=100, deadline=None)
@given(st.lists(secret_values, min_size=6, max_size=6, unique=True))
def test_plan_and_dry_run_hold_names_not_values(values) -> None:
    """**Validates: Requirements 12.7, 14.4, 14.6**"""
    names = list(deploy.WHATSAPP_NAMES) + ["EXPLAINER", "MERCHANT_CATEGORY"]
    lines = [f"{n}={v}" for n, v in zip(names, values)]
    lines.append(f"PAYSTACK_SECRET_KEY={KEY_PREFIX}{values[0]}")
    plan = deploy.format_plan(names, 7, 1234)
    code, printed = _run(lines, ["--dry-run"])
    assert code == 0
    for value in values:
        assert value not in plan and value not in printed
    assert "WHATSAPP_APP_SECRET" in printed and "PAYSTACK_SECRET_KEY" in printed


@settings(max_examples=100, deadline=None)
@given(secret_values, secret_values)
def test_error_messages_hold_no_values(bad_key, token) -> None:
    """**Validates: Requirements 14.6**"""
    lines = [f"PAYSTACK_SECRET_KEY={bad_key}", f"WHATSAPP_TOKEN={token}"]
    code, printed = _run(lines, ["--dry-run"])
    assert code == 1
    assert bad_key not in printed and token not in printed
    code, printed = _run(
        [f"PAYSTACK_SECRET_KEY={KEY_PREFIX}{bad_key}", f"WHATSAPP_TOKEN={token}"], []
    )
    assert code == 1
    assert bad_key not in printed and token not in printed
    assert "WHATSAPP_APP_SECRET" in printed
