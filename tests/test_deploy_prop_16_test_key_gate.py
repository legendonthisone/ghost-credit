"""Feature: whatsapp-webhook, Property 16: Only test keys pass the gate."""

from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

from deploy_helpers import load_deploy_module

deploy = load_deploy_module()

PREFIX = "sk_" + "test_"
candidates = st.one_of(
    st.text(max_size=30),
    st.text(max_size=20).map(lambda s: PREFIX + s),
    st.text(max_size=20).map(lambda s: "sk_" + "live_" + s),
    st.just(""),
    st.just("sk_"),
    st.just(PREFIX[:-1]),
)


@settings(max_examples=200, deadline=None)
@given(candidates)
def test_is_test_key_matches_the_prefix(value) -> None:
    """**Validates: Requirements 14.1**"""
    assert deploy.is_test_key(value) == value.startswith(PREFIX)


@settings(max_examples=100, deadline=None)
@given(candidates)
def test_gate_stops_before_any_aws_call(value) -> None:
    """**Validates: Requirements 14.1, 14.2**"""
    calls: list[int] = []
    original = deploy._deploy
    deploy._deploy = lambda *a, **k: calls.append(1)
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fake.env"
            path.write_text(f"PAYSTACK_SECRET_KEY={value}\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = deploy.main(["--env-file", str(path)])
    finally:
        deploy._deploy = original
    assert calls == []  # no AWS call, whatever the key
    if not value.strip().startswith(PREFIX):
        assert code == 1


def test_missing_key_stops() -> None:
    """A missing key stops the run before any AWS call."""
    assert deploy.is_test_key(None) is False
    assert deploy.is_test_key(123) is False
