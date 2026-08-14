"""API 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    course_id: int | None = None
    history: list[dict] = Field(default_factory=list)
    session_id: int | None = None


class CreateChatSessionRequest(BaseModel):
    course_id: int | None = None


class ChatSessionOut(BaseModel):
    id: int
    title: str
    course_id: int | None
    message_count: int = 0
    created_at: str
    updated_at: str


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class GenerateQuestionsRequest(BaseModel):
    course_id: int
    topic: str = ""
    count: int = Field(default=5, ge=1, le=20)
    qtype: str = Field(default="mixed", pattern="^(single|multiple|short|mixed)$")


class GradeRequest(BaseModel):
    question_id: int
    user_answer: str = Field(min_length=1)


class CourseOut(BaseModel):
    id: int
    name: str
    description: str
    document_count: int = 0


class DocumentOut(BaseModel):
    id: int
    course_id: int
    course_name: str
    filename: str
    doc_type: str
    chunk_count: int
    created_at: str


class QuestionOut(BaseModel):
    id: int
    course_id: int
    qtype: str
    topic: str
    stem: str
    options: list[str]
    answer: str
    explanation: str
