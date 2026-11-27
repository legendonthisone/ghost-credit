"""Example tests for the Lab additions to the deploy script. Fake clients only."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from deploy_helpers import load_deploy_module

deploy = load_deploy_module()
ROOT = Path(__file__).resolve().parents[1]


class AwsError(Exception):
    """A fake AWS error carrying a code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeWaiter:
    def __init__(self, log: list, name: str) -> None:
        self.log, self.name = log, name

    def wait(self, **kwargs) -> None:
        self.log.append(("wait", self.name, kwargs))


class FakeDynamo:
    """Records calls; ``exists`` says whether describe_table finds the table."""

    def __init__(self, exists: bool, ttl_error: str | None = None) -> None:
        self.exists, self.ttl_error = exists, ttl_error
        self.log: list[tuple] = []

    def describe_table(self, **kwargs):
        self.log.append(("describe_table", kwargs))
        if not self.exists:
            raise AwsError("ResourceNotFoundException")
        return {}

    def create_table(self, **kwargs):
        self.log.append(("create_table", kwargs))

    def get_waiter(self, name):
        return FakeWaiter(self.log, name)

    def update_time_to_live(self, **kwargs):
        self.log.append(("update_time_to_live", kwargs))
        if self.ttl_error:
            raise AwsError(self.ttl_error)


def _names(client: FakeDynamo) -> list[str]:
    return [entry[0] for entry in client.log]


def test_missing_table_is_created_then_ttl_enabled() -> None:
    client = FakeDynamo(exists=False)
    deploy._ensure_checks_table(client)
    assert _names(client) == ["describe_table", "create_table", "wait", "update_time_to_live"]
    create = dict(client.log[1][1])
    assert create["TableName"] == "ghost-credit-checks"
    assert create["BillingMode"] == "PAY_PER_REQUEST"
    assert create["AttributeDefinitions"] == [{"AttributeName": "check_id", "AttributeType": "S"}]
    assert create["KeySchema"] == [{"AttributeName": "check_id", "KeyType": "HASH"}]
    assert client.log[3][1] == {
        "TableName": "ghost-credit-checks",
        "TimeToLiveSpecification": {"Enabled": True, "AttributeName": "expires_at"},
    }


def test_existing_table_is_not_recreated() -> None:
    client = FakeDynamo(exists=True, ttl_error="ValidationException")
    deploy._ensure_checks_table(client)
    assert "create_table" not in _names(client)
    assert "update_time_to_live" in _names(client)


def test_other_table_errors_are_not_hidden() -> None:
    client = FakeDynamo(exists=True, ttl_error="AccessDeniedException")
    with pytest.raises(AwsError):
        deploy._ensure_checks_table(client)


def test_concurrency_success_call_shape(capsys) -> None:
    class Client:
        calls: list[dict] = []

        def put_function_concurrency(self, **kwargs):
            self.calls.append(kwargs)

    client = Client()
    assert deploy._set_reserved_concurrency(client) is True
    assert client.calls == [
        {"FunctionName": "ghost-credit", "ReservedConcurrentExecutions": 5}
    ]
    assert capsys.readouterr().out == ""


def test_lab_json_is_in_the_real_package_zip() -> None:
    with zipfile.ZipFile(io.BytesIO(deploy.build_zip(ROOT / "src" / "ghost_credit"))) as z:
        assert "ghost_credit/lab_sample.json" in z.namelist()
        assert "ghost_credit/lab_router.py" in z.namelist()


def test_json_file_is_kept_but_decoys_still_excluded(tmp_path) -> None:
    package = tmp_path / "ghost_credit"
    for folder in ("tests", "__pycache__", ".hypothesis"):
        (package / folder).mkdir(parents=True)
        (package / folder / "x.json").write_text("{}")
    (package / "data.json").write_text("[]")
    (package / ".env").write_text("A=1")
    (package / "m.pyc").write_bytes(b"0")
    with zipfile.ZipFile(io.BytesIO(deploy.build_zip(package))) as z:
        assert z.namelist() == ["ghost_credit/data.json"]


def test_variable_names_include_checks_table() -> None:
    assert "CHECKS_TABLE" in deploy.LAMBDA_VARIABLE_NAMES
    assert deploy.select_lambda_variables({})["CHECKS_TABLE"] == "ghost-credit-checks"
    assert deploy.RESERVED_CONCURRENCY == 5
