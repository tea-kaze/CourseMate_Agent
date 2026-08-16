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

