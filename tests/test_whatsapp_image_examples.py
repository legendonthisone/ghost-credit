"""Examples for image messages in the WhatsApp webhook. Fakes only: no Meta, no AWS."""
from __future__ import annotations

import base64
import json
import logging
from types import SimpleNamespace

import pytest

from ghost_credit import whatsapp
from ghost_credit.lab import InMemoryCheckStore
from ghost_credit.parser import ParsedAlert
from ghost_credit.paystack import UNAVAILABLE, PaystackResult
from ghost_credit.screenshot import MAX_VISION_IMAGE_BYTES, VisionScreenshotReader
from ghost_credit.verdict import TemplateExplainer
from ghost_credit.whatsapp import ASK_FOR_SMS_REPLY, USER_AGENT
from vision_fakes import GOOD_REPLY, MARKER, FakeBedrock, jpeg_payload, png_payload
from whatsapp_fakes import (
    ACCESS_TOKEN, RecordingGet, RecordingSend, fake_env, image_message, post, text_message,
    to_bytes, wrap_messages,
)

ID_URL = "https://graph.facebook.com/v21.0/media-1"
FILE_URL = "https://lookaside.example.test/file-1"
REPLY = "UNVERIFIED. Check your own bank app before releasing goods."


def _routes(image: bytes, mime: str = "image/jpeg", file_url: str = FILE_URL) -> dict:
    """Return recorded-style responses for the two media calls."""
    info = {"url": file_url, "mime_type": mime, "id": "media-1", "file_size": len(image)}
    return {ID_URL: (200, json.dumps(info).encode()), FILE_URL: (200, image)}


class SeeingCheck:
    """A fake run_check that records its input and returns a prepared parsed alert."""

    def __init__(self, amount_kobo: int | None = 4_500_000) -> None:
        self.calls: list[tuple] = []
        self.amount_kobo = amount_kobo

    def __call__(self, text, sender_id, image_bytes, category, now, **kwargs):
        self.calls.append((text, sender_id, image_bytes))
        return SimpleNamespace(reply=REPLY, parsed=ParsedAlert(amount_kobo=self.amount_kobo))


def _go(message: dict, **deps):
    deps.setdefault("send", RecordingSend())
    with fake_env():
        response = post(to_bytes(wrap_messages([message])), **deps)
    return response, deps["send"]


def _reply(send: RecordingSend) -> str:
    assert len(send.calls) == 1
    return send.sent_bodies()[0]["text"]["body"]


def test_image_is_fetched_then_checked() -> None:
    """GET /{media-id}, then the download, both with the token and our User-Agent."""
    image = jpeg_payload()
    get, check = RecordingGet(_routes(image)), SeeingCheck()
    response, send = _go(image_message(), get=get, check=check)
    assert response.status == 200
    assert [call[0] for call in get.calls] == [ID_URL, FILE_URL]
    for _, headers, _, _ in get.calls:
        assert headers["Authorization"] == "Bearer " + ACCESS_TOKEN
        assert headers["User-Agent"] == USER_AGENT
    assert check.calls == [("", None, image)]
    assert _reply(send) == REPLY


def test_caption_is_used_as_text() -> None:
    """A caption goes to the check as text next to the image."""
    message = image_message()
    message["image"]["caption"] = "NGN 45,000.00 received, please release"
    image = png_payload()
    check = SeeingCheck(amount_kobo=None)
    _, send = _go(message, get=RecordingGet(_routes(image, "image/png")), check=check)
    assert check.calls == [("NGN 45,000.00 received, please release", None, image)]
    assert _reply(send) == REPLY


@pytest.mark.parametrize(
    "get",
    [
        RecordingGet(raises=RuntimeError("down")),
        RecordingGet({}),  # 404 on the media URL call
        RecordingGet({ID_URL: (200, b"not json")}),
        RecordingGet({ID_URL: (200, b"[]")}),
        RecordingGet(_routes(b"x", mime="image/webp")),
        RecordingGet(_routes(b"x", mime="application/pdf")),
        RecordingGet(_routes(b"x", file_url="http://insecure.example.test/f")),
        RecordingGet({**_routes(b"x"), FILE_URL: (404, b"")}),
        RecordingGet({**_routes(b"x"), FILE_URL: (200, b"")}),
        RecordingGet(_routes(b"\x00" * (MAX_VISION_IMAGE_BYTES + 1))),
    ],
)
def test_failed_download_asks_for_the_sms(get: RecordingGet) -> None:
    """Any download problem gives the usual ask and no check."""
    check = SeeingCheck()
    response, send = _go(image_message(), get=get, check=check)
    assert response.status == 200
    assert check.calls == []
    assert _reply(send) == ASK_FOR_SMS_REPLY


def test_unreadable_screenshot_asks_for_the_sms() -> None:
    """No amount read and no caption: ask for the SMS text instead of a verdict."""
    check = SeeingCheck(amount_kobo=None)
    _, send = _go(image_message(), get=RecordingGet(_routes(jpeg_payload())), check=check)
    assert len(check.calls) == 1
    assert _reply(send) == ASK_FOR_SMS_REPLY


def test_no_token_means_no_download() -> None:
    """Without a WhatsApp token nothing is fetched."""
    get, check = RecordingGet(_routes(jpeg_payload())), SeeingCheck()
    with fake_env(WHATSAPP_TOKEN=None):
        post(to_bytes(wrap_messages([image_message()])), get=get, check=check,
             send=RecordingSend())
    assert get.calls == [] and check.calls == []


@pytest.mark.parametrize("media", [None, "junk", {}, {"id": 5}, {"id": ""}, {"id": "a/b"}, {"id": "x" * 101}])
def test_image_without_a_usable_media_id_is_not_fetched(media: object) -> None:
    """A bad media id is treated as other media: the ask, and no request."""
    message = {"from": "2348000000001", "id": "wamid.IMGX", "type": "image"}
    if media is not None:
        message["image"] = media
    get = RecordingGet(_routes(jpeg_payload()))
    _, send = _go(message, get=get, check=SeeingCheck())
    assert get.calls == []
    assert _reply(send) == ASK_FOR_SMS_REPLY


def test_text_message_never_touches_media() -> None:
    """Text messages are unchanged and make no media request."""
    get, check = RecordingGet(raises=AssertionError("no media call")), SeeingCheck()
    _, send = _go(text_message("NGN 5,000.00 CR"), get=get, check=check)
    assert get.calls == []
    assert check.calls == [("NGN 5,000.00 CR", None, None)]
    assert _reply(send) == REPLY


def test_other_media_types_still_get_the_ask_without_a_fetch() -> None:
    """Audio, documents and so on are never downloaded."""
    message = {"from": "2348000000001", "id": "wamid.AUD", "type": "audio",
               "audio": {"id": "media-1", "mime_type": "audio/ogg"}}
    get = RecordingGet(_routes(b"x"))
    _, send = _go(message, get=get, check=SeeingCheck())
    assert get.calls == [] and _reply(send) == ASK_FOR_SMS_REPLY


def test_end_to_end_with_the_vision_reader_and_fakes() -> None:
    """Real pipeline, fake Bedrock, fake Meta: an image alone ends at UNVERIFIED."""
    image = png_payload()
    bedrock = FakeBedrock(GOOD_REPLY)
    unavailable = PaystackResult(UNAVAILABLE, False, None, None, None, "no Paystack key set")
    store = InMemoryCheckStore()
    _, send = _go(
        image_message(),
        get=RecordingGet(_routes(image, "image/png")),
        reader=VisionScreenshotReader(bedrock),
        paystack_verify=lambda parsed, now: unavailable,
        explainer=TemplateExplainer(),
        store=store,
    )
    assert len(bedrock.calls) == 1
    reply = _reply(send)
    assert "bank app" in reply
    assert "ALIVE" not in reply
    records = store.newest(10)
    assert len(records) == 1 and records[0]["verdict"] != "CONFIRMED"


def test_image_bytes_reach_no_log_no_store_and_no_reply(caplog: pytest.LogCaptureFixture) -> None:
    """Across success and failure paths, the pixels appear nowhere but the model call."""
    caplog.set_level(logging.DEBUG)
    image = png_payload()
    unavailable = PaystackResult(UNAVAILABLE, False, None, None, None, "no Paystack key set")
    store = InMemoryCheckStore()
    outputs = []
    runs = [
        (RecordingGet(_routes(image, "image/png")), FakeBedrock(GOOD_REPLY)),
        (RecordingGet(_routes(image, "image/png")), FakeBedrock("not json")),
        (RecordingGet(_routes(image, "image/png")), FakeBedrock(raises=RuntimeError(repr(image)))),
        (RecordingGet(raises=RuntimeError(repr(image))), FakeBedrock(GOOD_REPLY)),
    ]
    for index, (get, bedrock) in enumerate(runs):
        message = image_message(message_id=f"wamid.LOG{index}")
        _, send = _go(
            message, get=get, reader=VisionScreenshotReader(bedrock),
            paystack_verify=lambda parsed, now: unavailable,
            explainer=TemplateExplainer(), store=store,
        )
        outputs.append(json.dumps(send.sent_bodies()))
    everything = caplog.text + json.dumps(store.newest(50), default=str) + "".join(outputs)
    assert MARKER.decode() not in everything
    assert base64.b64encode(image).decode() not in everything
    assert "b'" not in caplog.text
    assert whatsapp.USER_AGENT == "ghost-credit/0.1"
