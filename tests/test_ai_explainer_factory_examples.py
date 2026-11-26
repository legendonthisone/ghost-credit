"""Examples for the EXPLAINER environment switch. No boto3, no network."""

from __future__ import annotations

import pytest

from ai_explainer_helpers import FakeClient, make_parsed, make_verdict
from ghost_credit.ai_explainer import BedrockExplainer, get_explainer
from ghost_credit.verdict import TemplateExplainer


@pytest.mark.parametrize("value", ["bedrock", " Bedrock ", "BEDROCK"])
def test_bedrock_values(value: str) -> None:
    assert isinstance(get_explainer({"EXPLAINER": value}), BedrockExplainer)


@pytest.mark.parametrize("env", [{"EXPLAINER": "template"}, {"EXPLAINER": ""},
                                 {"EXPLAINER": "gpt"}, {}, {"OTHER": "bedrock"}])
def test_other_values_give_template(env: dict) -> None:
    assert isinstance(get_explainer(env), TemplateExplainer)


def test_none_env_reads_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXPLAINER", raising=False)
    assert isinstance(get_explainer(), TemplateExplainer)
    monkeypatch.setenv("EXPLAINER", "bedrock")
    assert isinstance(get_explainer(), BedrockExplainer)


def test_injected_client_reaches_explainer() -> None:
    client = FakeClient("reply", text="Take care.")
    explainer = get_explainer({"EXPLAINER": "bedrock"}, client=client)
    explainer.explain(make_verdict("SUSPICIOUS", ["The date looks wrong."]), make_parsed(), [])
    assert len(client.calls) == 1


def test_unset_explainer_makes_no_call() -> None:
    client = FakeClient("reply", text="Take care.")
    explainer = get_explainer({}, client=client)
    explainer.explain(make_verdict("SUSPICIOUS", ["The date looks wrong."]), make_parsed(), [])
    assert client.calls == []
