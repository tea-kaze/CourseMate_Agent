"""课程问答编排：会话解析、上下文压缩、调用 Agent、落库。"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessageChunk
from loguru import logger
from sqlalchemy.orm import Session

from coursemate.agent import context
from coursemate.db import chat_repo
from coursemate.db.repo import get_course


class SessionNotFound(Exception):
    pass


class CourseNotFound(Exception):
    pass


class SessionCourseConflict(Exception):
    pass


def _resolve_session(db: Session, course_id: int | None, session_id: int | None):
    if session_id is None:
        if course_id is not None and get_course(db, course_id) is None:
            raise CourseNotFound("课程不存在")
        chat_session = chat_repo.create_chat_session(db, course_id=course_id)
    else:
        chat_session = chat_repo.get_chat_session(db, session_id)
        if chat_session is None:
            raise SessionNotFound("会话不存在")
        if course_id is not None and course_id != chat_session.course_id:
            raise SessionCourseConflict("会话课程范围与请求不一致，请新建会话后切换课程")
    db.flush()
    return chat_session, chat_session.course_id


def run_chat(
    db: Session,
    *,
    message: str,
    course_id: int | None = None,
    session_id: int | None = None,
    history: list[dict] | None = None,
    agent: Any | None = None,
    llm: Any | None = None,
) -> dict:
    """执行一轮问答：解析/创建会话 → 压缩上下文 → 调 Agent → 落库。"""
    chat_session, effective_course_id = _resolve_session(db, course_id, session_id)

    if session_id is None and history:
        # 兼容旧调用方：未指定会话时沿用请求携带的历史
        history_msgs = [
            {"role": role, "content": content}
            for role, content in history
            if role in {"user", "assistant"} and content
        ]
    else:
        history_msgs = [
            {"role": m.role, "content": m.content}
            for m in chat_repo.list_chat_messages(db, chat_session.id)
        ]
    ctx_msgs, new_summary = context.build_chat_context(
        history_msgs, chat_session.summary, llm=llm
    )

    raw_message = message
    agent_messages = list(ctx_msgs)
    agent_messages.append({"role": "user", "content": message})

    if agent is None:
        from coursemate.agent.agent import build_agent

        agent = build_agent(effective_course_id)
    result = agent.invoke(
        {"messages": agent_messages},
        config={
            "metadata": {
                "flow": "chat",
                "session_id": chat_session.id,
                "course_id": effective_course_id,
            }
        },
    )
    messages = result.get("messages", [])
    answer = messages[-1].content if messages else ""

    chat_repo.add_chat_message(db, chat_session.id, "user", raw_message)
    chat_repo.add_chat_message(db, chat_session.id, "assistant", answer)
    if new_summary != chat_session.summary:
        chat_repo.update_chat_session_summary(db, chat_session.id, new_summary)
    db.flush()
    return {
        "answer": answer,
        "session_id": chat_session.id,
        "session_title": chat_session.title,
    }


def run_chat_stream(
    db: Session,
    *,
    message: str,
    course_id: int | None = None,
    session_id: int | None = None,
    history: list[dict] | None = None,
    agent: Any | None = None,
    llm: Any | None = None,
):
    """流式问答：逐 token 产出事件，流结束后统一落库。

    与 run_chat 的差异：Agent 用 stream_mode="messages" 逐 token 输出，
    只对外流式返回最终回答（跳过工具调用块与思考 token——二者 content 为空
    或带 tool_calls）；用户消息、助手完整回答、摘要仍在流结束后写入数据库。

    产出事件（生成器）：
    - {"type": "meta", "session_id": int}  —— 首条，携带会话 ID
    - {"type": "token", "content": str}    —— 回答 token
    - {"type": "error", "message": str}    —— 流中途失败（此时不落库）
    """
    chat_session, effective_course_id = _resolve_session(db, course_id, session_id)

    if session_id is None and history:
        history_msgs = [
            {"role": role, "content": content}
            for role, content in history
            if role in {"user", "assistant"} and content
        ]
    else:
        history_msgs = [
            {"role": m.role, "content": m.content}
            for m in chat_repo.list_chat_messages(db, chat_session.id)
        ]
    ctx_msgs, new_summary = context.build_chat_context(
        history_msgs, chat_session.summary, llm=llm
    )

    raw_message = message
    agent_messages = list(ctx_msgs)
    agent_messages.append({"role": "user", "content": message})

    if agent is None:
        from coursemate.agent.agent import build_agent

        agent = build_agent(effective_course_id)

    yield {"type": "meta", "session_id": chat_session.id}

    answer_parts: list[str] = []
    try:
        for chunk in agent.stream(
            {"messages": agent_messages},
            config={
                "metadata": {
                    "flow": "chat_stream",
                    "session_id": chat_session.id,
                    "course_id": effective_course_id,
                }
            },
            stream_mode="messages",
        ):
            msg, _meta = chunk
            content = msg.content
            if (
                isinstance(msg, AIMessageChunk)
                and isinstance(content, str)
                and content
                and not msg.tool_calls
            ):
                answer_parts.append(content)
                yield {"type": "token", "content": content}
    except Exception as exc:  # noqa: BLE001
        logger.exception("流式问答失败")
        yield {"type": "error", "message": str(exc)}
        return

    answer = "".join(answer_parts)
    chat_repo.add_chat_message(db, chat_session.id, "user", raw_message)
    chat_repo.add_chat_message(db, chat_session.id, "assistant", answer)
    if new_summary != chat_session.summary:
        chat_repo.update_chat_session_summary(db, chat_session.id, new_summary)
    db.flush()
