from __future__ import annotations

from langchain_core.messages import AIMessageChunk
import pytest

from coursemate.app import chat_service
from coursemate.db import chat_repo
from coursemate.db import repo


def _agent(answer: str = "答案是A"):
    class FakeAgent:
        def invoke(self, state, config=None):
            msgs = state["messages"]
            msgs.append(type("M", (), {"role": "assistant", "content": answer})())
            return {"messages": msgs}

    return FakeAgent()


def test_run_chat_creates_session_and_saves_messages(fresh_db):
    course = repo.get_or_create_course(fresh_db, "操作系统")
    result = chat_service.run_chat(
        fresh_db,
        message="什么是进程调度？",
        course_id=course.id,
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
    course = repo.get_or_create_course(fresh_db, "操作系统")
    s = chat_repo.create_chat_session(fresh_db, course_id=course.id)
    chat_repo.add_chat_message(fresh_db, s.id, "user", "旧问题")
    chat_repo.add_chat_message(fresh_db, s.id, "assistant", "旧回答")

    class FakeAgent:
        def invoke(self, state, config=None):
            msgs = state["messages"]
            contents = [m["content"] for m in msgs if isinstance(m, dict)]
            assert "旧问题" in contents
            assert "不应使用" not in contents
            msgs.append(type("M", (), {"role": "assistant", "content": "新回答"})())
            return {"messages": msgs}

    result = chat_service.run_chat(
        fresh_db,
        message="继续",
        course_id=course.id,
        session_id=s.id,
        history=[{"role": "user", "content": "不应使用"}],
        agent=FakeAgent(),
    )
    fresh_db.commit()
    assert len(chat_repo.list_chat_messages(fresh_db, s.id)) == 4
    assert result["session_id"] == s.id


def test_run_chat_uses_request_history_for_new_session(fresh_db):
    class FakeAgent:
        def invoke(self, state, config=None):
            contents = [
                message["content"]
                for message in state["messages"]
                if isinstance(message, dict)
            ]
            assert contents[-3:] == ["old question", "old answer", "follow up"]
            state["messages"].append(
                type("M", (), {"role": "assistant", "content": "new answer"})()
            )
            return state

    result = chat_service.run_chat(
        fresh_db,
        message="follow up",
        session_id=None,
        history=[
            {"role": "user", "content": "old question"},
            {"role": "assistant", "content": "old answer"},
        ],
        agent=FakeAgent(),
    )

    assert result["answer"] == "new answer"


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
        def invoke(self, state, config=None):
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


def test_run_chat_failure_preserves_new_session(fresh_db):
    class BoomAgent:
        def invoke(self, state, config=None):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        chat_service.run_chat(
            fresh_db,
            message="hello",
            course_id=None,
            session_id=None,
            history=[],
            agent=BoomAgent(),
        )

    fresh_db.rollback()
    sessions = chat_repo.list_chat_sessions(fresh_db)
    assert len(sessions) == 1
    assert chat_repo.list_chat_messages(fresh_db, sessions[0]["id"]) == []


def _stream_agent(chunks):
    """构造按给定 chunk 列表逐条产出消息的假 Agent（stream 模式）。"""

    class FakeAgent:
        def stream(self, state, stream_mode=None, config=None):
            for c in chunks:
                yield (c, {})

    return FakeAgent()


def test_run_chat_stream_yields_tokens_and_saves_messages(fresh_db):
    course = repo.get_or_create_course(fresh_db, "操作系统")
    events = list(
        chat_service.run_chat_stream(
            fresh_db,
            message="什么是进程调度？",
            course_id=course.id,
            session_id=None,
            history=[],
            agent=_stream_agent(
                [AIMessageChunk(content="你好"), AIMessageChunk(content="，同学")]
            ),
        )
    )
    fresh_db.commit()

    types = [e["type"] for e in events]
    assert types == ["meta", "token", "token"]
    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    assert tokens == "你好，同学"

    sid = events[0]["session_id"]
    msgs = chat_repo.list_chat_messages(fresh_db, sid)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].content == "你好，同学"


def test_run_chat_rejects_course_change_for_existing_session(fresh_db):
    course_a = repo.get_or_create_course(fresh_db, "操作系统")
    course_b = repo.get_or_create_course(fresh_db, "数据库")
    session = chat_repo.create_chat_session(fresh_db, course_id=course_a.id)

    with pytest.raises(chat_service.SessionCourseConflict):
        chat_service.run_chat(
            fresh_db,
            message="问题",
            course_id=course_b.id,
            session_id=session.id,
            agent=_agent(),
        )


def test_run_chat_uses_bound_course_and_keeps_user_message_raw(
    fresh_db, monkeypatch
):
    course = repo.get_or_create_course(fresh_db, "操作系统")
    session = chat_repo.create_chat_session(fresh_db, course_id=course.id)
    built_with: list[int | None] = []

    class FakeAgent:
        def invoke(self, state, config=None):
            assert state["messages"][-1]["content"] == "什么是调度？"
            assert config["metadata"]["course_id"] == course.id
            state["messages"].append(
                type("M", (), {"role": "assistant", "content": "回答"})()
            )
            return state

    from coursemate.agent import agent as agent_module

    monkeypatch.setattr(
        agent_module,
        "build_agent",
        lambda course_id=None: built_with.append(course_id) or FakeAgent(),
    )

    chat_service.run_chat(
        fresh_db,
        message="什么是调度？",
        course_id=None,
        session_id=session.id,
    )

    assert built_with == [course.id]


def test_run_chat_stream_skips_tool_call_chunks(fresh_db):
    events = list(
        chat_service.run_chat_stream(
            fresh_db,
            message="hi",
            course_id=None,
            session_id=None,
            history=[],
            agent=_stream_agent(
                [
                    AIMessageChunk(content=""),  # 思考阶段，无正文
                    AIMessageChunk(
                        content="被跳过的正文",
                        tool_calls=[{"name": "search", "args": {}, "id": "1"}],
                    ),  # 工具调用块，正文不应流出
                    AIMessageChunk(content="最终回答"),
                ]
            ),
        )
    )
    fresh_db.commit()

    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    assert tokens == "最终回答"


def test_run_chat_stream_error_does_not_save(fresh_db):
    class BoomAgent:
        def stream(self, state, stream_mode=None, config=None):
            yield (AIMessageChunk(content="前半"), {})
            raise RuntimeError("boom")

    events = list(
        chat_service.run_chat_stream(
            fresh_db,
            message="hi",
            course_id=None,
            session_id=None,
            history=[],
            agent=BoomAgent(),
        )
    )
    fresh_db.commit()

    types = [e["type"] for e in events]
    assert "token" in types
    assert types[-1] == "error"
    assert "boom" in events[-1]["message"]

    sid = events[0]["session_id"]
    # 流中途失败：不落库任何消息
    assert chat_repo.list_chat_messages(fresh_db, sid) == []


def test_run_chat_stream_error_preserves_emitted_session_id(fresh_db):
    class BoomAgent:
        def stream(self, state, stream_mode=None, config=None):
            raise RuntimeError("boom")
            yield

    events = list(
        chat_service.run_chat_stream(
            fresh_db,
            message="hello",
            course_id=None,
            session_id=None,
            history=[],
            agent=BoomAgent(),
        )
    )
    sid = events[0]["session_id"]

    fresh_db.rollback()
    assert chat_repo.get_chat_session(fresh_db, sid) is not None
    assert chat_repo.list_chat_messages(fresh_db, sid) == []
