"""SQLAlchemy ORM 模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DocumentStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    INGEST_FAILED = "ingest_failed"
    DELETING = "deleting"
    DELETE_FAILED = "delete_failed"


class Course(Base):
    """课程：资料和题目按课程组织，检索时可按课程过滤。"""
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class Document(Base):
    """文档：记录上传的文件、存放路径与切分后的片段数量。

    chunk_count 用于展示与排查：入库后能确认切分是否正常。
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(300))
    file_path: Mapped[str] = mapped_column(String(500))
    doc_type: Mapped[str] = mapped_column(String(20))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.PENDING, index=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    course: Mapped[Course] = relationship(back_populates="documents")


class Question(Base):
    """题目：出题后持久化，供批改与错题本使用。

    - options 存选择题选项（JSON 数组），简答题为空；
    - answer 存参考答案，批改时作为对照。
    """
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    qtype: Mapped[str] = mapped_column(String(20))  # single | multiple | short
    topic: Mapped[str] = mapped_column(String(200), default="")
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    course: Mapped[Course] = relationship(back_populates="questions")
    attempts: Mapped[list["AnswerAttempt"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class AnswerAttempt(Base):
    """作答记录：一次提交一条，是错题统计的数据来源。"""
    __tablename__ = "answer_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    user_answer: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    question: Mapped[Question] = relationship(back_populates="attempts")


class ChatSession(Base):
    """问答会话：持久化用户与助手的多轮对话，支持上下文压缩摘要。"""
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    """问答消息：归属某个会话，按时间升序。"""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped[ChatSession] = relationship(back_populates="messages")
