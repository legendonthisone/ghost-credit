"""Examples for VisionScreenshotReader. A fake Bedrock client only: no AWS call."""
from __future__ import annotations

import ast
import base64
import logging
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest

from ghost_credit import screenshot
from ghost_credit.parser import ParsedAlert
from ghost_credit.screenshot import (
    MAX_VISION_IMAGE_BYTES,
    FakeScreenshotReader,
    VisionScreenshotReader,
    get_screenshot_reader,
)
from vision_fakes import (
    GOOD_REPLY, JPEG_MAGIC, MARKER, FakeBedrock, converse_reply, jpeg_payload, png_payload,
)

EMPTY = ParsedAlert()


def test_recorded_image_gives_the_fields_and_the_right_request() -> None:
    """A good reply fills the fields; the request has the model, limits and bytes."""
    client = FakeBedrock(GOOD_REPLY)
    image = png_payload()
    alert = VisionScreenshotReader(client).read(image)
    assert alert.amount_kobo == 4_500_000
    assert alert.currency == "NGN"
    assert alert.claimed_bank == "GTBank"
    assert alert.claimed_reference == "REF-SYN-001"
    assert alert.alert_time == datetime(2026, 11, 20, 10, 2, 11)
    assert alert.available_balance_kobo == 12_000_000
    assert alert.sender_id is None and alert.red_flags == []
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["modelId"] == "amazon.nova-lite-v1:0"
    assert call["inferenceConfig"]["maxTokens"] == 300
    block = call["messages"][0]["content"][0]["image"]
    assert block["format"] == "png" and block["source"]["bytes"] == image
    assert "JSON" in call["system"][0]["text"]


def test_jpeg_is_sent_as_jpeg() -> None:
    """The file type comes from the bytes."""
    client = FakeBedrock(GOOD_REPLY)
    VisionScreenshotReader(client).read(jpeg_payload())
    assert client.calls[0]["messages"][0]["content"][0]["image"]["format"] == "jpeg"


def test_client_is_built_with_region_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real client path asks for bedrock-runtime, us-east-1 and a 10 s timeout."""
    made: list[tuple] = []
    config_args: list[dict] = []

    def fake_client(name: str, **kwargs: object) -> FakeBedrock:
        made.append((name, kwargs))
        return FakeBedrock(GOOD_REPLY)

    def fake_config(**kwargs: object) -> dict:
        config_args.append(kwargs)
        return kwargs

    boto3 = types.ModuleType("boto3")
    boto3.client = fake_client  # type: ignore[attr-defined]
    config_module = types.ModuleType("botocore.config")
    config_module.Config = fake_config  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setitem(sys.modules, "botocore", types.ModuleType("botocore"))
    monkeypatch.setitem(sys.modules, "botocore.config", config_module)
    assert VisionScreenshotReader().read(png_payload()).amount_kobo == 4_500_000
    assert [name for name, _ in made] == ["bedrock-runtime"]
    assert made[0][1]["region_name"] == "us-east-1"
    assert config_args[0]["read_timeout"] == 10 and config_args[0]["connect_timeout"] == 10


@pytest.mark.parametrize(
    "text",
    [
        '```json\n{"amount": "5,000.00", "currency": "NGN"}\n```',
        'Here is the JSON: {"amount": "5,000.00", "currency": "NGN"} Hope it helps.',
    ],
)
def test_json_wrapped_in_fences_or_words_is_still_read(text: str) -> None:
    """Fences or a leading sentence do not stop the parse."""
    alert = VisionScreenshotReader(FakeBedrock(text)).read(png_payload())
    assert alert.amount_kobo == 500_000 and alert.currency == "NGN"


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("45,000.00", 4_500_000),
        ("NGN 45,000.00", 4_500_000),
        ("₦45,000.50", 4_500_050),
        ("45000", 4_500_000),
        (45000, 4_500_000),
        (45000.5, 4_500_050),
        ("4,5,000", None),
        ("45,000.005", None),
        ("-5,000", None),
        ("about 5000", None),
        ("", None),
        (None, None),
        (True, None),
        ([1], None),
        ("9" * 40, None),
    ],
)
def test_amount_is_converted_strictly(amount: object, expected: int | None) -> None:
    """Only a plain naira amount becomes kobo; anything else is None, never a guess."""
    reply = {**GOOD_REPLY, "amount": amount}
    alert = VisionScreenshotReader(FakeBedrock(reply)).read(png_payload())
    assert alert.amount_kobo == expected


def test_missing_fields_stay_none() -> None:
    """Nothing is guessed: absent and null values stay None."""
    alert = VisionScreenshotReader(FakeBedrock({"amount": "1,000.00", "bank": None})).read(
        png_payload()
    )
    assert alert.amount_kobo == 100_000
    assert alert.currency is None and alert.claimed_bank is None
    assert alert.claimed_reference is None and alert.alert_time is None
    assert alert.available_balance_kobo is None


def test_model_cannot_set_flags_sender_or_verdict() -> None:
    """Extra keys in the reply are ignored."""
    reply = {
        **GOOD_REPLY,
        "red_flags": ["DATE_ODD"],
        "sender_id": "GTBANK",
        "verdict": "CONFIRMED",
        "edit_signs": True,
    }
    alert = VisionScreenshotReader(FakeBedrock(reply)).read(png_payload())
    assert alert.red_flags == [] and alert.sender_id is None


@pytest.mark.parametrize(
    "reply",
    ["not json at all", "", "[1, 2, 3]", "null", "{broken", "x" * 25_000,
     '{"amount": ' + "[" * 5000],
)
def test_bad_model_json_gives_an_empty_alert(reply: str) -> None:
    """Bad JSON never raises and never half-fills an alert."""
    assert VisionScreenshotReader(FakeBedrock(reply)).read(png_payload()) == EMPTY


@pytest.mark.parametrize(
    "response",
    [{}, {"output": None}, {"output": {"message": {"content": []}}},
     {"output": {"message": {"content": [{"image": 1}]}}}, None, "text"],
)
def test_odd_response_shapes_give_an_empty_alert(response: object) -> None:
    """A reply in an unexpected shape gives an empty alert."""

    class Odd:
        def converse(self, **kwargs: object) -> object:
            return response

    assert VisionScreenshotReader(Odd()).read(png_payload()) == EMPTY


@pytest.mark.parametrize("error", [TimeoutError("slow"), RuntimeError("boom"), OSError("net")])
def test_client_errors_give_an_empty_alert(error: Exception) -> None:
    """Any client error, including a timeout, gives an empty alert."""
    assert VisionScreenshotReader(FakeBedrock(raises=error)).read(png_payload()) == EMPTY


def test_oversized_image_is_refused_without_a_model_call() -> None:
    """One byte over the limit makes no call; exactly the limit is allowed."""
    client = FakeBedrock(GOOD_REPLY)
    reader = VisionScreenshotReader(client)
    too_big = png_payload(b"\x00" * (MAX_VISION_IMAGE_BYTES - 8 + 1))
    assert len(too_big) == MAX_VISION_IMAGE_BYTES + 1
    assert reader.read(too_big) == EMPTY and client.calls == []
    at_limit = png_payload(b"\x00" * (MAX_VISION_IMAGE_BYTES - 8))
    assert reader.read(at_limit).amount_kobo == 4_500_000 and len(client.calls) == 1


@pytest.mark.parametrize(
    "payload",
    [b"", b"GIF89a....", b"RIFF....WEBPVP8 ", b"%PDF-1.4", "text", None, 123, bytearray(JPEG_MAGIC + b"x")],
)
def test_wrong_type_or_empty_makes_no_model_call(payload: object) -> None:
    """Only real JPEG and PNG bytes are sent to the model."""
    client = FakeBedrock(GOOD_REPLY)
    assert VisionScreenshotReader(client).read(payload) == EMPTY  # type: ignore[arg-type]
    assert client.calls == []


def test_no_image_bytes_reach_any_log(caplog: pytest.LogCaptureFixture) -> None:
    """Logs hold step names and error types, never image bytes or model text."""
    caplog.set_level(logging.DEBUG)
    image = png_payload()
    secret_text = "MODEL-SAID-SECRET-TEXT"
    errors = [RuntimeError(repr(image)), TimeoutError(base64.b64encode(image).decode())]
    cases = [
        FakeBedrock(GOOD_REPLY),
        FakeBedrock("not json " + secret_text),
        FakeBedrock(raises=errors[0]),
        FakeBedrock(raises=errors[1]),
    ]
    for client in cases:
        VisionScreenshotReader(client).read(image)
    VisionScreenshotReader(FakeBedrock(GOOD_REPLY)).read(b"\x00" + image)  # wrong type
    text = caplog.text
    assert MARKER.decode() not in text
    assert base64.b64encode(image).decode() not in text
    assert secret_text not in text and "b'" not in text
    assert "vision step" in text and "RuntimeError" in text


def test_reader_source_has_no_disk_or_store_calls() -> None:
    """screenshot.py never opens a file or names S3 or DynamoDB."""
    source = Path(screenshot.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    opens = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "open"]
    assert opens == []
    lowered = source.lower()
    for word in ("s3", "dynamodb", "tempfile", "write_bytes", ".save("):
        assert word not in lowered.replace("tests3", "")


def test_boto3_is_not_imported_at_module_level() -> None:
    """Importing the module loads no AWS library."""
    tree = ast.parse(Path(screenshot.__file__).read_text(encoding="utf-8"))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert "boto3" not in names and "botocore" not in names


def test_factory_defaults_to_the_fake_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the exact setting 'vision' turns the model on."""
    monkeypatch.delenv("SCREENSHOT_READER", raising=False)
    assert isinstance(get_screenshot_reader(), FakeScreenshotReader)
    for value in ("fake", "", "visio", "1", "true"):
        monkeypatch.setenv("SCREENSHOT_READER", value)
        assert isinstance(get_screenshot_reader(), FakeScreenshotReader)
    for value in ("vision", " Vision "):
        monkeypatch.setenv("SCREENSHOT_READER", value)
        assert isinstance(get_screenshot_reader(), VisionScreenshotReader)


def test_converse_reply_helper_shape() -> None:
    """Guard the fake itself: the reply shape matches Bedrock Converse."""
    assert converse_reply("hi")["output"]["message"]["content"][0]["text"] == "hi"
