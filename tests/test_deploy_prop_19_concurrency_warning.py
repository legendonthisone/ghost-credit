"""The Lab, Property 17: a reserved-concurrency failure never stops the deploy."""

from __future__ import annotations

import contextlib
import io

from hypothesis import given, settings, strategies as st

from deploy_helpers import load_deploy_module

deploy = load_deploy_module()


class InvalidParameterValueException(Exception):
    """Stands in for the AWS error of the same name."""


class LimitExceededException(Exception):
    """Stands in for the AWS error of the same name."""


class OddFailure(Exception):
    """Any other failure type."""


class FakeLambdaClient:
    """Raises the given exception from put_function_concurrency."""

    def __init__(self, exc: Exception | None) -> None:
        self.exc = exc
        self.calls: list[dict] = []

    def put_function_concurrency(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return {}


def _error(kind: type, code: str) -> Exception:
    exc = kind("fake failure")
    exc.response = {"Error": {"Code": code}}  # type: ignore[attr-defined]
    return exc


exceptions = st.one_of(
    st.just(_error(InvalidParameterValueException, "InvalidParameterValueException")),
    st.just(_error(LimitExceededException, "LimitExceededException")),
    st.just(OddFailure("odd")),
    st.just(RuntimeError("plain")),
    st.just(ValueError("plain")),
)


# Feature: the-lab, Property 17: A reserved-concurrency failure is reported and never stops the deploy
# **Validates: Requirements 9.7**
@settings(max_examples=100, deadline=None)
@given(exceptions)
def test_failure_prints_warning_naming_the_exception_and_returns(exc) -> None:
    client = FakeLambdaClient(exc)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = deploy._set_reserved_concurrency(client)
    assert result is False
    printed = out.getvalue()
    assert "WARNING" in printed and type(exc).__name__ in printed
    assert len(client.calls) == 1
