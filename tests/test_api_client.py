from __future__ import annotations

import httpx
import pytest

from coursemate.web import api_client


def test_get_courses_reports_non_json_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            text="Internal Server Error",
            headers={"content-type": "text/plain; charset=utf-8"},
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        api_client,
        "_client",
        lambda: httpx.Client(base_url="http://test", transport=transport),
    )
    api_client.get_courses.clear()

    with pytest.raises(RuntimeError, match="HTTP 500.*Internal Server Error"):
        api_client.get_courses()


def test_chat_stream_reads_http_error_body(monkeypatch):
    class ErrorStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"detail":"session not found"}'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            headers={"content-type": "application/json"},
            stream=ErrorStream(),
        )

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)

    def client_factory(*args, **kwargs):
        return real_client(base_url="http://test", transport=transport)

    monkeypatch.setattr(api_client.httpx, "Client", client_factory)

    with pytest.raises(RuntimeError, match="HTTP 404.*session not found"):
        list(api_client.chat_stream("hello", session_id=999))
