"""Feature: ai-explainer, Property 9: The factory defaults to template."""

from __future__ import annotations

import sys

from hypothesis import given, settings, strategies as st

from ghost_credit.ai_explainer import BedrockExplainer, get_explainer
from ghost_credit.verdict import TemplateExplainer

_values = st.one_of(
    st.text(max_size=12),
    st.sampled_from(["bedrock", " Bedrock ", "BEDROCK\n", "template", "", "gpt", "bedrock2"]),
    st.none(), st.integers(), st.lists(st.text(max_size=3), max_size=2),
)
_envs = st.one_of(
    st.dictionaries(st.sampled_from(["EXPLAINER", "OTHER", "explainer"]), _values, max_size=3),
    st.just({}),
)


# **Validates: Requirements 7.1, 7.2, 7.3, 7.5, 7.6**
@settings(max_examples=200, deadline=None)
@given(env=_envs)
def test_factory_defaults_to_template(env) -> None:
    before = "boto3" in sys.modules
    result = get_explainer(env)
    value = env.get("EXPLAINER")
    wants_bedrock = isinstance(value, str) and value.strip().lower() == "bedrock"
    assert isinstance(result, BedrockExplainer) == wants_bedrock
    if not wants_bedrock:
        assert isinstance(result, TemplateExplainer)
    assert ("boto3" in sys.modules) == before


class _Broken(dict):
    def get(self, *args, **kwargs):
        raise RuntimeError("broken mapping")


def test_broken_mapping_gives_template() -> None:
    assert isinstance(get_explainer(_Broken()), TemplateExplainer)
