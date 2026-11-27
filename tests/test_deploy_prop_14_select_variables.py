"""Feature: whatsapp-webhook, Property 14: Variable selection keeps only the allowed names."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from deploy_helpers import load_deploy_module

deploy = load_deploy_module()

allowed = list(deploy.LAMBDA_VARIABLE_NAMES)
any_name = st.one_of(st.sampled_from(allowed), st.text(min_size=1, max_size=12))
mappings = st.dictionaries(any_name, st.one_of(st.just(""), st.text(max_size=20)), max_size=12)


@settings(max_examples=200, deadline=None)
@given(mappings)
def test_only_allowed_names_with_the_right_defaults(values) -> None:
    """**Validates: Requirements 12.4, 12.5, 12.6**"""
    selected = deploy.select_lambda_variables(values)
    assert set(selected) <= set(allowed)
    assert all(value != "" for value in selected.values())
    assert selected["PATTERN_NETWORK"] == "off"
    assert selected["MERCHANT_CATEGORY"] == (values.get("MERCHANT_CATEGORY") or "other")
    assert selected["EXPLAINER"] == (values.get("EXPLAINER") or "template")
    assert selected["CHECKS_TABLE"] == (values.get("CHECKS_TABLE") or "ghost-credit-checks")
    assert selected["USED_REFS_TABLE"] == (
        values.get("USED_REFS_TABLE") or "ghost-credit-used-refs"
    )
    for name in allowed:
        if name in (
            "PATTERN_NETWORK", "MERCHANT_CATEGORY", "EXPLAINER", "CHECKS_TABLE",
            "USED_REFS_TABLE",
        ):
            continue
        if values.get(name):
            assert selected[name] == values[name]
        else:
            assert name not in selected
