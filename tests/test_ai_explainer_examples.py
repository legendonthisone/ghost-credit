"""Examples for BedrockExplainer. Fakes only: no Bedrock, no boto3, no network."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from ai_explainer_helpers import FakeClient, ReadTimeoutError, make_parsed, make_verdict, reply_with
from test_ai_explainer_prop_05_request_settings import fake_aws
from ghost_credit.ai_explainer import BedrockExplainer
from ghost_credit.verdict import TemplateExplainer

VERDICT = make_verdict("SUSPICIOUS", ["The date looks wrong."])
NOTES = ["Take extra care."]


def _template() -> str:
    return TemplateExplainer().explain(VERDICT, make_parsed(), NOTES)


def test_success_with_recorded_reply() -> None:
    client = FakeClient()
    client.converse = lambda **kw: reply_with("The date on this alert looks odd.")  # type: ignore[method-assign]
    out = BedrockExplainer(client=client).explain(VERDICT, make_parsed(), NOTES)
    headline = _template().split("\n", 1)[0]
    assert out == headline + "\n\nThe date on this alert looks odd."


def test_timeout_falls_back_to_template() -> None:
    client = FakeClient("raise", exc=ReadTimeoutError("slow"))
    out = BedrockExplainer(client=client).explain(VERDICT, make_parsed(), NOTES)
    assert out == _template()


def test_guard_rejection_falls_back() -> None:
    client = FakeClient("reply", text="Your payment is real.")
    assert BedrockExplainer(client=client).explain(VERDICT, make_parsed(), NOTES) == _template()


def test_boto3_blocked_falls_back_and_module_still_imports() -> None:
    with mock.patch.dict(sys.modules, {"boto3": None}):
        out = BedrockExplainer().explain(VERDICT, make_parsed(), NOTES)
    assert out == _template()
    src = str(Path(__file__).resolve().parent.parent / "src")
    code = "import sys; sys.modules['boto3'] = None; import ghost_credit.ai_explainer"
    done = subprocess.run([sys.executable, "-c", code], env={**os.environ, "PYTHONPATH": src},
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr


def test_fake_boto3_records_config_and_region() -> None:
    client = FakeClient("reply", text="Take care.")
    created: list = []
    configs: list = []
    with mock.patch.dict(sys.modules, fake_aws(client, created, configs)):
        BedrockExplainer(region="eu-west-1").explain(VERDICT, make_parsed(), NOTES)
    assert configs == [{"read_timeout": 5, "connect_timeout": 5, "retries": {"max_attempts": 0}}]
    assert created[0][0] == "bedrock-runtime"
    assert created[0][1]["region_name"] == "eu-west-1"


def test_injected_client_never_imports_boto3() -> None:
    client = FakeClient("reply", text="Take care.")
    with mock.patch.dict(sys.modules, {"boto3": None}):
        out = BedrockExplainer(client=client).explain(VERDICT, make_parsed(), NOTES)
    assert out.endswith("\n\nTake care.")
    assert len(client.calls) == 1


def test_fallback_log_holds_only_exception_type_name(caplog) -> None:
    secret_reason = "The date looks wrong. SECRETREASON"
    verdict = make_verdict("SUSPICIOUS", [secret_reason])
    client = FakeClient("raise", exc=ReadTimeoutError("prompt text SECRETMSG"))
    with caplog.at_level(logging.DEBUG, logger="ghost_credit.ai_explainer"):
        BedrockExplainer(client=client).explain(verdict, make_parsed(), ["SECRETNOTE"])
    records = [r for r in caplog.records if r.name == "ghost_credit.ai_explainer"]
    assert len(records) == 1
    assert records[0].getMessage() == "ai explainer fallback: ReadTimeoutError"
    assert records[0].exc_info is None
    assert "SECRET" not in caplog.text


def test_guard_rejected_and_no_usable_text_log_fixed_words(caplog) -> None:
    with caplog.at_level(logging.DEBUG, logger="ghost_credit.ai_explainer"):
        BedrockExplainer(client=FakeClient("reply", text="money is real")).explain(VERDICT, None, NOTES)
        BedrockExplainer(client=FakeClient("bad_shape")).explain(VERDICT, None, NOTES)
    messages = [r.getMessage() for r in caplog.records]
    assert messages == ["ai explainer fallback: GuardRejected", "ai explainer fallback: NoUsableText"]
