"""课程问答页面的会话管理行为测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from coursemate.web import api_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QA_PAGE = PROJECT_ROOT / "coursemate/web/pages/2_💬_课程问答.py"

COURSES = [{"id": 2, "name": "操作系统", "description": "", "document_count": 1}]
SESSIONS = [
    {
        "id": 1,
        "title": "什么是进程调度？",
        "course_id": None,
        "message_count": 2,
        "created_at": "2026-08-14T00:00:00",
        "updated_at": "2026-08-14T00:00:00",
    }
]
MESSAGES = [
    {
        "id": 1,
        "role": "user",
        "content": "什么是进程调度？",
        "created_at": "2026-08-14T00:00:00",
    },
    {
        "id": 2,
        "role": "assistant",
        "content": "进程调度是……",
        "created_at": "2026-08-14T00:00:00",
    },
]


@pytest.fixture()
def page(monkeypatch: pytest.MonkeyPatch):
    calls: dict = {"chat": [], "create": [], "delete": []}

    def fake_courses():
        return COURSES

    def fake_list_sessions():
        return SESSIONS

    def fake_list_messages(session_id):
        return MESSAGES

    def fake_create(course_id=None):
        calls["create"].append(course_id)
        return {
            "id": 2,
            "title": "新会话",
            "course_id": course_id,
            "message_count": 0,
            "created_at": "2026-08-14T00:00:00",
            "updated_at": "2026-08-14T00:00:00",
        }

    def fake_delete(session_id):
        calls["delete"].append(session_id)

    def fake_chat(message, course_id=None, history=None, session_id=None):
        calls["chat"].append((message, course_id, session_id))
        return {
            "answer": "新回答",
            "session_id": session_id,
            "session_title": "什么是进程调度？",
        }

    monkeypatch.setattr(api_client, "get_courses", fake_courses)
    monkeypatch.setattr(api_client, "list_chat_sessions", fake_list_sessions)
    monkeypatch.setattr(api_client, "list_chat_messages", fake_list_messages)
    monkeypatch.setattr(api_client, "create_chat_session", fake_create)
    monkeypatch.setattr(api_client, "delete_chat_session", fake_delete)
    monkeypatch.setattr(api_client, "chat", fake_chat)

    at = AppTest.from_file(str(QA_PAGE), default_timeout=10)
    at.run()
    return at, calls


def test_page_loads_most_recent_session_messages(page):
    at, calls = page
    md = [m.value for m in at.markdown]
    assert any("什么是进程调度？" in t for t in md)
    assert any("进程调度是……" in t for t in md)


def test_new_session_creates_and_switches(page):
    at, calls = page
    at.button(key="new_session").click().run()
    assert calls["create"] == [None]
    assert any(b.key == "session_1" for b in at.button)


def test_delete_current_session(page):
    at, calls = page
    at.button(key="delete_current").click().run()
    assert calls["delete"] == [1]


def test_send_message_calls_chat_with_session_id(page):
    at, calls = page
    at.chat_input[0].set_value("什么是死锁？").run()
    assert calls["chat"] == [("什么是死锁？", None, 1)]
