"""Example tests and smoke checks for the deploy script. No AWS, no boto3."""

from __future__ import annotations

import io
import subprocess
import sys
import zipfile
from pathlib import Path

from deploy_helpers import SCRIPT, load_deploy_module

deploy = load_deploy_module()
ROOT = Path(__file__).resolve().parents[1]
KEY = "sk_" + "test_" + "zz-fake-0000"


def _no_aws(*args, **kwargs):
    raise AssertionError("AWS must not be called")


def test_permission_policy_is_least_privilege() -> None:
    """Only the four allowed actions, on the right resources."""
    policy = deploy.permissions_policy("111122223333")
    actions: list[str] = []
    for statement in policy["Statement"]:
        found = statement["Action"]
        actions += [found] if isinstance(found, str) else found
    assert sorted(actions) == [
        "bedrock:InvokeModel", "logs:CreateLogGroup",
        "logs:CreateLogStream", "logs:PutLogEvents",
    ]
    bedrock, logs = policy["Statement"]
    assert bedrock["Resource"] == (
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-micro-v1:0"
    )
    assert logs["Resource"] == (
        "arn:aws:logs:us-east-1:111122223333:log-group:/aws/lambda/ghost-credit:*"
    )


def test_trust_policy_names_only_lambda() -> None:
    """Only the Lambda service may assume the role."""
    statement = deploy.trust_policy()["Statement"]
    assert len(statement) == 1
    assert statement[0]["Principal"] == {"Service": "lambda.amazonaws.com"}


def test_constants_match_the_requirements() -> None:
    """Runtime, handler, timeout and memory."""
    assert (deploy.RUNTIME, deploy.TIMEOUT_SECONDS, deploy.MEMORY_MB) == ("python3.12", 30, 256)
    assert deploy.HANDLER == "ghost_credit.lambda_handler.lambda_handler"


def test_zip_leaves_out_decoys(tmp_path) -> None:
    """Decoy files and folders never reach the zip."""
    package = tmp_path / "ghost_credit"
    (package / "tests").mkdir(parents=True)
    (package / "__pycache__").mkdir()
    (package / ".hypothesis").mkdir()
    (package / "sub").mkdir()
    (package / "a.py").write_text("x = 1")
    (package / "sub" / "b.py").write_text("y = 2")
    (package / ".env").write_text("A=1")
    (package / "tests" / "t.py").write_text("t")
    (package / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"0")
    (package / "sub" / "stray.pyc").write_bytes(b"0")
    (package / ".hypothesis" / "h").write_text("h")
    with zipfile.ZipFile(io.BytesIO(deploy.build_zip(package))) as archive:
        names = archive.namelist()
    assert sorted(names) == ["ghost_credit/a.py", "ghost_credit/sub/b.py"]


def test_real_package_zip_is_clean() -> None:
    """The real package zip starts with ghost_credit/ and holds no decoys."""
    with zipfile.ZipFile(io.BytesIO(deploy.build_zip(ROOT / "src" / "ghost_credit"))) as z:
        names = z.namelist()
    assert "ghost_credit/lambda_handler.py" in names
    assert all(n.startswith("ghost_credit/") for n in names)
    assert not any(
        "/tests/" in n or "__pycache__" in n or n.endswith(".pyc") or ".env" in n
        or ".hypothesis" in n for n in names
    )


def test_dry_run_makes_no_aws_call_and_prints_names(tmp_path, monkeypatch, capsys) -> None:
    """A dry run with fake values prints names only."""
    env = tmp_path / "fake.env"
    env.write_text(f"PAYSTACK_SECRET_KEY={KEY}\nWHATSAPP_TOKEN=fake-token-value-1\n")
    monkeypatch.setattr(deploy, "_deploy", _no_aws)
    assert deploy.main(["--dry-run", "--env-file", str(env)]) == 0
    printed = capsys.readouterr().out
    assert "WHATSAPP_TOKEN" in printed and "WHATSAPP_VERIFY_TOKEN" in printed
    assert "fake-token-value-1" not in printed and KEY not in printed


def test_live_looking_key_stops_before_aws(tmp_path, monkeypatch, capsys) -> None:
    """A key without the test prefix stops the run."""
    env = tmp_path / "fake.env"
    env.write_text("PAYSTACK_SECRET_KEY=" + "sk_" + "live_" + "zz-fake-0000\n")
    monkeypatch.setattr(deploy, "_deploy", _no_aws)
    assert deploy.main(["--env-file", str(env)]) == 1
    assert "PAYSTACK_SECRET_KEY" in capsys.readouterr().out


def test_deploy_mode_stops_when_whatsapp_names_missing(tmp_path, monkeypatch, capsys) -> None:
    """Deploy mode stops before AWS when a WhatsApp variable is missing."""
    env = tmp_path / "fake.env"
    env.write_text(f"PAYSTACK_SECRET_KEY={KEY}\n")
    monkeypatch.setattr(deploy, "_deploy", _no_aws)
    assert deploy.main(["--env-file", str(env)]) == 1
    assert "WHATSAPP_VERIFY_TOKEN" in capsys.readouterr().out


def test_imports_with_boto3_blocked() -> None:
    """The script imports even when boto3 cannot be imported."""
    code = (
        "import sys, importlib.util\n"
        "class B:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in ('boto3', 'botocore'):\n"
        "            raise ImportError(name)\n"
        "sys.meta_path.insert(0, B())\n"
        f"s = importlib.util.spec_from_file_location('d', r'{SCRIPT}')\n"
        "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
        "print('ok')\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"


def test_source_has_no_whole_test_key_prefix_literal() -> None:
    """The prefix is built from pieces, so it never appears whole."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "sk_" + "test_" not in source
    assert "boto3" in source and "import boto3" not in source.split("def _deploy")[0]
