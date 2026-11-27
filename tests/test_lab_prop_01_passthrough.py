"""Property 1: the router is a total, correct passthrough for non-Lab paths."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit import lambda_handler as lh
from ghost_credit.whatsapp import WebhookResponse

_paths = st.one_of(
    st.just("/"),
    st.just("/webhook"),
    st.text(max_size=30).filter(lambda p: not p.startswith("/lab")),
    st.text(max_size=30).map(lambda s: "/x" + s),
)
_methods = st.sampled_from(["GET", "POST", "PUT", "DELETE", "get", ""])
_bodies = st.one_of(st.none(), st.text(max_size=200))
_queries = st.one_of(st.none(), st.dictionaries(st.text(max_size=8), st.text(max_size=8), max_size=3))
_headers = st.one_of(
    st.none(), st.dictionaries(st.text(max_size=10), st.text(max_size=10), max_size=3)
)


# Feature: the-lab, Property 1: The router is a total, correct passthrough for non-Lab paths
# **Validates: Requirements 1.1, 1.2, 1.4**
@settings(max_examples=100, deadline=None)
@given(_paths, _methods, _bodies, _queries, _headers, st.integers(0, 599), st.text(max_size=40))
def test_non_lab_paths_reach_handle_webhook_unchanged(
    path, method, body, query, headers, status, reply_body
):
    calls: list[tuple] = []
    answer = WebhookResponse(status, reply_body)

    def fake(m, q, h, raw, **deps):
        calls.append((m, q, h, raw))
        return answer

    original = lh.handle_webhook
    lh.handle_webhook = fake
    try:
        event = {
            "rawPath": path,
            "requestContext": {"http": {"method": method}},
            "queryStringParameters": query,
            "headers": headers,
            "body": body,
        }
        out = lh.lambda_handler(event, None)
    finally:
        lh.handle_webhook = original
    assert len(calls) == 1
    assert calls[0][0] == method and calls[0][1] == query
    assert calls[0][3] == (body.encode("utf-8") if body is not None else b"")
    assert out == {
        "statusCode": int(answer.status),
        "headers": {"content-type": answer.content_type},
        "body": str(answer.body),
    }
