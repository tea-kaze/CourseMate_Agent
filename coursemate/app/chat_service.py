"""课程问答编排：会话解析、上下文压缩、调用 Agent、落库。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from coursemate.agent import context
from coursemate.db import chat_repo


class SessionNotFound(Exception):
    pass


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
    if session_id is None:
        chat_session = chat_repo.create_chat_session(db, course_id=course_id)
    else:
        chat_session = chat_repo.get_chat_session(db, session_id)
        if chat_session is None:
            raise SessionNotFound("会话不存在")
    db.flush()

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
    if course_id:
        message = f"[课程范围：{course_id}] {message}"
    agent_messages = list(ctx_msgs)
    agent_messages.append({"role": "user", "content": message})

    if agent is None:
        from coursemate.agent.agent import build_agent

        agent = build_agent()
    result = agent.invoke({"messages": agent_messages})
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
