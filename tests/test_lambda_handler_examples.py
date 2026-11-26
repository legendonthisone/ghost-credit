"""Example tests for the Lambda adapter. No network, no AWS."""

from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

from ghost_credit import lambda_handler as lh
from ghost_credit import whatsapp
from whatsapp_fakes import (
    ACCESS_TOKEN, VERIFY_TOKEN, FakeCheck, RecordingSend, sign, set_env,
    text_message, to_bytes, wrap_messages,
)

SRC = str(Path(__file__).resolve().parents[1] / "src")


def test_get_verification_event(monkeypatch) -> None:
    """A v2.0 GET with the right token returns the challenge."""
    set_env(monkeypatch)
    event = {
        "requestContext": {"http": {"method": "GET"}},
        "queryStringParameters": {
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "12345",
        },
    }
    result = lh.lambda_handler(event, None)
    assert result["statusCode"] == 200
    assert result["body"] == "12345"


def test_signed_post_with_base64_body(monkeypatch) -> None:
    """A signed base64 POST reaches the check and sends one reply."""
    set_env(monkeypatch)
    send, check = RecordingSend(), FakeCheck()
    body = to_bytes(wrap_messages([text_message("Credit alert NGN 5,000.00", message_id="wamid.L1")]))
    event = {
        "requestContext": {"http": {"method": "POST"}},
        "headers": {"X-Hub-Signature-256": sign(body)},
        "body": base64.b64encode(body).decode("ascii"),
        "isBase64Encoded": True,
    }
    real = whatsapp.handle_webhook
    monkeypatch.setattr(
        lh, "handle_webhook", lambda *a, **k: real(*a, send=send, check=check, **k)
    )
    result = lh.lambda_handler(event, None)
    assert result["statusCode"] == 200
    assert len(check.calls) == 1 and len(send.calls) == 1
    assert ACCESS_TOKEN in send.calls[0][1]["Authorization"]


def test_unsigned_post_is_forbidden(monkeypatch) -> None:
    """A POST with no signature gets 403."""
    set_env(monkeypatch)
    event = {"requestContext": {"http": {"method": "POST"}}, "body": "{}"}
    result = lh.lambda_handler(event, None)
    assert result["statusCode"] == 403
    assert result["body"] == "forbidden"


def test_non_dict_event_is_forbidden() -> None:
    """A non-dict event gets the fixed 403."""
    assert lh.lambda_handler("nope", None)["statusCode"] == 403
    assert lh.lambda_handler(None, None)["body"] == "forbidden"


def test_imports_with_image_libraries_blocked() -> None:
    """The adapter imports when PIL and imagehash cannot be imported."""
    code = (
        "import sys\n"
        "class B:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in ('PIL','imagehash','numpy','scipy'):\n"
        "            raise ImportError(name)\n"
        "sys.meta_path.insert(0, B())\n"
        "import ghost_credit.lambda_handler\n"
        "print('ok')\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        env={"PYTHONPATH": SRC, "PATTERN_NETWORK": "off", "SYSTEMROOT": "C:\\Windows"},
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"
