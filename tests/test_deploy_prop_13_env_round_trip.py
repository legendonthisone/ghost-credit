"""Feature: whatsapp-webhook, Property 13: Env file parsing round trips."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from deploy_helpers import load_deploy_module

deploy = load_deploy_module()

names = st.from_regex(r"[A-Z][A-Z0-9_]{0,15}", fullmatch=True)
values = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=#_-.:/ +",
    max_size=40,
).filter(lambda v: v == v.strip())
comments = st.text(alphabet="abc xyz123", max_size=20).map(lambda s: "# " + s)
fillers = st.lists(st.one_of(st.just(""), st.just("   "), comments), max_size=3)


@settings(max_examples=150, deadline=None)
@given(st.dictionaries(names, values, max_size=8), st.data())
def test_parse_returns_what_was_written(mapping, data) -> None:
    """**Validates: Requirements 12.3**"""
    lines: list[str] = []
    for name, value in mapping.items():
        lines.extend(data.draw(fillers))
        lines.append(f"{name}={value}")
    lines.extend(data.draw(fillers))
    assert deploy.parse_env_text("\n".join(lines)) == mapping


def test_matching_quotes_are_removed_once() -> None:
    """One pair of surrounding quotes goes; inner quotes stay."""
    parsed = deploy.parse_env_text("A=\"x\"\nB='y'\nC=\"'z'\"\nD=\"half")
    assert parsed == {"A": "x", "B": "y", "C": "'z'", "D": '"half'}
