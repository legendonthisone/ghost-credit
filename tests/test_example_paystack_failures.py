"""Example tests for Paystack failures, using recorded fake replies."""

from __future__ import annotations

from datetime import datetime

from ghost_credit.paystack import verify
from paystack_fakes import RecordingHttp, fake_key, make_parsed

NOW = datetime(2026, 11, 20, 10, 5, 0)
KEY = fake_key("example")


def _check(fake: RecordingHttp, reason: str, reference: str | None = "GC-1001") -> None:
    result = verify(make_parsed(claimed_reference=reference), KEY, NOW, http=fake)
    assert result.status == "UNAVAILABLE"
    assert result.checked is False
    assert result.reason == reason
    assert len(fake.calls) == 1


def test_timeout():
    _check(RecordingHttp(raises=TimeoutError("slow")), "could not reach Paystack")


def test_non_200_server_error():
    _check(RecordingHttp(status=500, body=b'{"message": "oops"}'),
           "Paystack did not answer normally")


NOT_FOUND_BODY = b'{"status": false, "message": "Transaction reference not found"}'


def _check_no_such_reference(fake: RecordingHttp) -> None:
    result = verify(make_parsed(claimed_reference="GC-1001"), KEY, NOW, http=fake)
    assert result.status == "NOT_FOUND"
    assert result.checked is True
    assert result.matched_reference is None
    assert result.amount_kobo is None
    assert result.paid_at is None
    assert result.reason == "Paystack has no payment with this reference"
    assert len(fake.calls) == 1


def test_404_not_found_gives_not_found():
    _check_no_such_reference(RecordingHttp(status=404, body=NOT_FOUND_BODY))


def test_400_not_found_gives_not_found():
    _check_no_such_reference(RecordingHttp(status=400, body=NOT_FOUND_BODY))


def test_400_other_message_stays_unavailable():
    body = b'{"status": false, "message": "Invalid key"}'
    _check(RecordingHttp(status=400, body=body), "Paystack did not answer normally")


def test_code_transaction_not_found_with_unrelated_message():
    body = b'{"status": false, "code": "transaction_not_found", "message": "Nope"}'
    _check_no_such_reference(RecordingHttp(status=404, body=body))


def test_404_on_search_path_stays_unavailable():
    _check(RecordingHttp(status=404, body=NOT_FOUND_BODY),
           "Paystack did not answer normally", reference=None)


def test_401_bad_key_reply():
    _check(RecordingHttp(status=401, body=b'{"status": false}'),
           "Paystack did not answer normally")


def test_malformed_json():
    _check(RecordingHttp(body=b"<html>gateway</html>"), "Paystack reply could not be read")


def test_json_not_an_object():
    _check(RecordingHttp(body=b"[1, 2, 3]"), "Paystack reply could not be read")


def test_missing_data_field():
    _check(RecordingHttp(body=b'{"status": true}'), "Paystack reply could not be read")


def test_list_data_for_reference_check():
    _check(RecordingHttp(body=b'{"data": []}'), "Paystack reply could not be read")


def test_object_data_for_search():
    _check(RecordingHttp(body=b'{"data": {}}'), "Paystack reply could not be read",
           reference=None)


def test_not_utf8_body():
    _check(RecordingHttp(body=b"\xff\xfe"), "Paystack reply could not be read")
