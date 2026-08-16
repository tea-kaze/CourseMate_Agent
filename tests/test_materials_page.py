from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from coursemate.web import api_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATERIALS_PAGE = PROJECT_ROOT / "coursemate/web/pages/1_📁_资料管理.py"


def test_materials_page_shows_backend_error(monkeypatch: pytest.MonkeyPatch):
    def fail_documents():
        raise RuntimeError("后端请求失败（HTTP 500）：Internal Server Error")

    monkeypatch.setattr(api_client, "get_documents", fail_documents)

    at = AppTest.from_file(str(MATERIALS_PAGE), default_timeout=10)
    at.run()

    assert not at.exception
    assert any("HTTP 500" in error.value for error in at.error)
