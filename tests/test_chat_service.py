from __future__ import annotations

from coursemate.app import chat_service
from coursemate.db import chat_repo


def _agent(answer: str = "答案是A"):
    class FakeAgent:
        def invoke(self, state):
            msgs = state["messages"]
            msgs.append(type("M", (), {"role": "assistant", "content": answer})())
            return {"messages": msgs}

    return FakeAgent()


def test_run_chat_creates_session_and_saves_messages(fresh_db):
    result = chat_service.run_chat(
        fresh_db,
        message="什么是进程调度？",
        course_id=2,
        session_id=None,
        history=[],
        agent=_agent(),
    )
    fresh_db.commit()
    assert result["session_id"] is not None
    assert result["answer"] == "答案是A"
    saved = chat_repo.get_chat_session(fresh_db, result["session_id"])
    assert saved.title == "什么是进程调度？"
    msgs = chat_repo.list_chat_messages(fresh_db, result["session_id"])
    assert [m.role for m in msgs] == ["user", "assistant"]


def test_run_chat_appends_to_existing_session_and_ignores_history(fresh_db):
    s = chat_repo.create_chat_session(fresh_db, course_id=2)
    chat_repo.add_chat_message(fresh_db, s.id, "user", "旧问题")
    chat_repo.add_chat_message(fresh_db, s.id, "assistant", "旧回答")

    class FakeAgent:
        def invoke(self, state):
            msgs = state["messages"]
            contents = [m["content"] for m in msgs if isinstance(m, dict)]
            assert "旧问题" in contents
            assert "不应使用" not in contents
            msgs.append(type("M", (), {"role": "assistant", "content": "新回答"})())
            return {"messages": msgs}

    result = chat_service.run_chat(
        fresh_db,
        message="继续",
        course_id=2,
        session_id=s.id,
        history=[{"role": "user", "content": "不应使用"}],
        agent=FakeAgent(),
    )
    fresh_db.commit()
    assert len(chat_repo.list_chat_messages(fresh_db, s.id)) == 4
    assert result["session_id"] == s.id


def test_run_chat_compresses_long_history_and_persists_summary(fresh_db):
    s = chat_repo.create_chat_session(fresh_db)
    for i in range(30):
        chat_repo.add_chat_message(
            fresh_db, s.id, "user" if i % 2 == 0 else "assistant", f"消息{i}"
        )

    class FakeLLM:
        def invoke(self, prompt):
            return type("R", (), {"content": "压缩摘要"})()

    class FakeAgent:
        def invoke(self, state):
            msgs = state["messages"]
            contents = [m["content"] for m in msgs if isinstance(m, dict)]
            assert any("压缩摘要" in c for c in contents)
            msgs.append(type("M", (), {"role": "assistant", "content": "ok"})())
            return {"messages": msgs}

    chat_service.run_chat(
        fresh_db,
        message="继续",
        course_id=None,
        session_id=s.id,
        history=[],
        agent=FakeAgent(),
        llm=FakeLLM(),
    )
    fresh_db.commit()
    assert chat_repo.get_chat_session(fresh_db, s.id).summary == "压缩摘要"


def test_run_chat_raises_when_session_missing(fresh_db):
    try:
        chat_service.run_chat(
            fresh_db,
            message="hi",
            course_id=None,
            session_id=999,
            history=[],
            agent=_agent(),
        )
    except chat_service.SessionNotFound:
        return
    raise AssertionError("会话不存在时应抛出 SessionNotFound")
