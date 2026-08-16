"""会话与消息的仓库函数。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from coursemate.db.models import ChatMessage, ChatSession, utc_isoformat, utcnow


def create_chat_session(
    session: Session, course_id: int | None = None, title: str = ""
) -> ChatSession:
    chat_session = ChatSession(course_id=course_id, title=title)
    session.add(chat_session)
    session.flush()
    return chat_session


def list_chat_sessions(session: Session) -> list[dict]:
    rows = session.execute(
        select(ChatSession, func.count(ChatMessage.id))
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
    ).all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "course_id": s.course_id,
            "message_count": count,
            "created_at": utc_isoformat(s.created_at),
            "updated_at": utc_isoformat(s.updated_at),
        }
        for s, count in rows
    ]


def get_chat_session(session: Session, session_id: int) -> ChatSession | None:
    return session.get(ChatSession, session_id)


def delete_chat_session(session: Session, chat_session: ChatSession) -> None:
    session.delete(chat_session)
    session.flush()


def add_chat_message(
    session: Session, session_id: int, role: str, content: str
) -> ChatMessage:
    chat_session = session.get(ChatSession, session_id)
    if chat_session is None:
        raise ValueError("会话不存在")
    msg = ChatMessage(session_id=session_id, role=role, content=content)
    session.add(msg)
    if role == "user" and not chat_session.title:
        chat_session.title = content[:20]
    chat_session.updated_at = utcnow()
    session.flush()
    return msg


def list_chat_messages(session: Session, session_id: int) -> list[ChatMessage]:
    return list(
        session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
    )


def update_chat_session_summary(
    session: Session, session_id: int, summary: str
) -> None:
    chat_session = session.get(ChatSession, session_id)
    if chat_session is None:
        raise ValueError("会话不存在")
    chat_session.summary = summary
    chat_session.updated_at = utcnow()
    session.flush()
