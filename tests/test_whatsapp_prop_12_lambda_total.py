"""Feature: whatsapp-webhook, Property 12: The Lambda adapter is total and well shaped."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.lambda_handler import lambda_handler
from whatsapp_fakes import fake_env

leaf = st.one_of(
    st.none(), st.booleans(), st.integers(), st.text(max_size=30), st.binary(max_size=20)
)
anything = st.recursive(
    leaf,
    lambda inner: st.one_of(
        st.lists(inner, max_size=4), st.dictionaries(st.text(max_size=12), inner, max_size=5)
    ),
    max_leaves=12,
)
shaped_events = st.fixed_dictionaries(
    {},
    optional={
        "requestContext": anything,
        "queryStringParameters": anything,
        "headers": anything,
        "body": anything,
        "isBase64Encoded": anything,
    },
)
events = st.one_of(anything, shaped_events)


@settings(max_examples=200, deadline=None)
@given(events)
def test_adapter_always_returns_a_well_shaped_dict(event) -> None:
    """**Validates: Requirements 11.4, 11.5, 11.6**"""
    with fake_env():
        result = lambda_handler(event, None)
    assert isinstance(result, dict)
    assert isinstance(result["statusCode"], int)
    assert isinstance(result["headers"], dict)
    assert isinstance(result["body"], str)
    assert result["statusCode"] in (200, 403, 405, 413)
