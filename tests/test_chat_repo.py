from __future__ import annotations

from coursemate.db import chat_repo


def test_create_and_list_chat_sessions_ordered_by_updated_at(fresh_db):
    s1 = chat_repo.create_chat_session(fresh_db, course_id=None, title="旧会话")
    s2 = chat_repo.create_chat_session(fresh_db, course_id=1, title="新会话")
    rows = chat_repo.list_chat_sessions(fresh_db)
    assert [r["id"] for r in rows] == [s2.id, s1.id]
    assert rows[0]["title"] == "新会话"
    assert rows[0]["message_count"] == 0


def test_add_message_touches_time_and_auto_titles_from_first_user_message(fresh_db):
    s = chat_repo.create_chat_session(fresh_db, course_id=None)
    chat_repo.add_chat_message(fresh_db, s.id, "user", "什么是进程调度？")
    chat_repo.add_chat_message(fresh_db, s.id, "assistant", "进程调度是……")
    saved = chat_repo.get_chat_session(fresh_db, s.id)
    assert saved.title == "什么是进程调度？"
    msgs = chat_repo.list_chat_messages(fresh_db, s.id)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert chat_repo.list_chat_sessions(fresh_db)[0]["message_count"] == 2


def test_delete_chat_session_cascades_messages(fresh_db):
    s = chat_repo.create_chat_session(fresh_db)
    chat_repo.add_chat_message(fresh_db, s.id, "user", "你好")
    chat_repo.delete_chat_session(fresh_db, s)
    assert chat_repo.get_chat_session(fresh_db, s.id) is None
    assert chat_repo.list_chat_messages(fresh_db, s.id) == []


def test_update_chat_session_summary(fresh_db):
    s = chat_repo.create_chat_session(fresh_db)
    chat_repo.update_chat_session_summary(fresh_db, s.id, "摘要内容")
    assert chat_repo.get_chat_session(fresh_db, s.id).summary == "摘要内容"
