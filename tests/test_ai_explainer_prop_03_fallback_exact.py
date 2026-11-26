"""Feature: ai-explainer, Property 3: Any failure returns exactly the template text."""

from __future__ import annotations

import sys
import types
from unittest import mock

from hypothesis import given, settings, strategies as st

from ai_explainer_helpers import (FakeClient, ReadTimeoutError, codes, make_parsed, make_verdict,
                                  notes_list, reasons_list)
from ghost_credit.ai_explainer import BedrockExplainer
from ghost_credit.verdict import TemplateExplainer

_FAILS = ["raise", "timeout", "bad_shape", "non_text", "empty_text", "blank_text",
          "guard_rejected", "no_boto3", "client_error", "no_clean_items"]
# Text that mentions a result a SUSPICIOUS or UNVERIFIED verdict cannot support.
_BAD_TEXT = "Your money has arrived and it is confirmed."


def _fake_boto3_that_fails() -> dict:
    boto3 = types.ModuleType("boto3")

    def _client(*args, **kwargs):
        raise RuntimeError("no credentials")

    boto3.client = _client  # type: ignore[attr-defined]
    botocore = types.ModuleType("botocore")
    config = types.ModuleType("botocore.config")
    config.Config = lambda **kw: kw  # type: ignore[attr-defined]
    return {"boto3": boto3, "botocore": botocore, "botocore.config": config}


# **Validates: Requirements 3.7, 6.1, 6.2, 6.3, 6.4, 6.5, 6.9, 8.6**
@settings(max_examples=200, deadline=None)
@given(code=st.sampled_from(["NOT_FOUND", "SUSPICIOUS", "UNVERIFIED"]), reasons=reasons_list,
       notes=notes_list, fail=st.sampled_from(_FAILS))
def test_any_failure_returns_template_text(code, reasons, notes, fail) -> None:
    verdict = make_verdict(code, reasons)
    parsed = make_parsed()
    if fail == "no_clean_items":
        verdict = make_verdict(code, [])
        notes = []
    elif not any(isinstance(x, str) and x.strip() for x in list(reasons) + list(notes)):
        reasons = ["A clean reason."]
        verdict = make_verdict(code, reasons)
    expected = TemplateExplainer().explain(verdict, parsed, notes)

    client = None
    modules: dict = {}
    if fail == "raise":
        client = FakeClient("raise")
    elif fail == "timeout":
        client = FakeClient("raise", exc=ReadTimeoutError("slow"))
    elif fail in ("bad_shape", "non_text"):
        client = FakeClient(fail)
    elif fail == "empty_text":
        client = FakeClient("reply", text="")
    elif fail == "blank_text":
        client = FakeClient("reply", text="  \n ")
    elif fail == "guard_rejected":
        client = FakeClient("reply", text=_BAD_TEXT)
    elif fail == "no_boto3":
        modules = {"boto3": None}
    elif fail == "client_error":
        modules = _fake_boto3_that_fails()
    else:
        client = FakeClient("reply", text="Take care.")

    with mock.patch.dict(sys.modules, modules):
        out = BedrockExplainer(client=client).explain(verdict, parsed, notes)
    assert out == expected
    if client is not None:
        assert len(client.calls) <= 1
        if fail == "no_clean_items":
            assert client.calls == []
