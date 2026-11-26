"""Feature: ai-explainer, Property 5: The request has the fixed settings."""

from __future__ import annotations

import sys
import types
from unittest import mock

from hypothesis import given, settings, strategies as st

from ai_explainer_helpers import FakeClient, codes, make_parsed, make_verdict
from ghost_credit.ai_explainer import BedrockExplainer

_clean_notes = st.lists(st.sampled_from(["Take extra care.", "Large amount.", "Late on Friday."]),
                        max_size=3)


def fake_aws(client: FakeClient, created: list, configs: list) -> dict:
    """Fake boto3 and botocore modules that record how the client is made."""
    boto3 = types.ModuleType("boto3")

    def _client(name, **kwargs):
        created.append((name, kwargs))
        return client

    boto3.client = _client  # type: ignore[attr-defined]
    botocore = types.ModuleType("botocore")
    config = types.ModuleType("botocore.config")

    def _config(**kwargs):
        configs.append(kwargs)
        return ("config", kwargs)

    config.Config = _config  # type: ignore[attr-defined]
    return {"boto3": boto3, "botocore": botocore, "botocore.config": config}


# **Validates: Requirements 2.1, 2.2, 2.3, 2.7, 8.6**
@settings(max_examples=100, deadline=None)
@given(code=codes, notes=_clean_notes,
       region=st.one_of(st.none(), st.sampled_from(["eu-west-1", "af-south-1", "us-east-1"])))
def test_request_has_fixed_settings(code, notes, region) -> None:
    client = FakeClient("reply", text="Take care with this alert.")
    created: list = []
    configs: list = []
    kwargs = {} if region is None else {"region": region}
    explainer = BedrockExplainer(**kwargs)
    with mock.patch.dict(sys.modules, fake_aws(client, created, configs)):
        explainer.explain(make_verdict(code, ["The date looks wrong."]), make_parsed(), notes)
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["modelId"] == "amazon.nova-micro-v1:0"
    assert call["inferenceConfig"] == {"maxTokens": 200}
    assert len(call["system"]) == 1
    assert len(call["messages"]) == 1 and call["messages"][0]["role"] == "user"
    assert created == [("bedrock-runtime", {"region_name": region or "us-east-1",
                                            "config": ("config", configs[0])})]
    assert configs == [{"read_timeout": 5, "connect_timeout": 5,
                        "retries": {"max_attempts": 0}}]
