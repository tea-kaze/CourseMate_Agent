"""FastAPI 应用与路由。"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger

from coursemate.agent.service import NoRelevantCourseMaterialError, get_service
from coursemate.app.ingestion import (
    DocumentDeletionError,
    DocumentNotFoundError,
    DocumentStateError,
    IngestionError,
    delete_document_consistently,
    delete_document_file,
    ingest_file,
)
from coursemate.app.chat_service import (
    CourseNotFound,
    SessionCourseConflict,
    SessionNotFound,
    run_chat,
    run_chat_stream,
)
from coursemate.app.schemas import (
    ChatMessageOut,
    ChatRequest,
    ChatSessionOut,
    CourseOut,
    CreateChatSessionRequest,
    DocumentOut,
    GenerateQuestionsRequest,
    GradeOut,
    GradeRequest,
    QuestionPublicOut,
)
from coursemate.config import get_settings
from coursemate.db import chat_repo
from coursemate.db.models import utc_isoformat
from coursemate.db.repo import (
    delete_document,
    get_document,
    get_or_create_course,
    get_question,
    list_courses,
    list_documents,
    mistake_stats,
    save_attempt,
    save_questions,
)
from coursemate.db.session import get_session, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path("data").mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("CourseMate API 启动完成")
    yield


app = FastAPI(
    title="CourseMate API",
    description="课程学习与刷题助手：资料入库、知识问答、自动出题、答题批改与错题统计",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

service = get_service()


def _to_course_out(course) -> CourseOut:
    return CourseOut(
        id=course.id,
        name=course.name,
        description=course.description,
        document_count=len(course.documents),
    )


def _to_document_out(doc) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        course_id=doc.course_id,
        course_name=doc.course.name,
        filename=doc.filename,
        doc_type=doc.doc_type,
        chunk_count=doc.chunk_count,
        created_at=utc_isoformat(doc.created_at),
    )


def _to_question_out(q) -> QuestionPublicOut:
    return QuestionPublicOut(
        id=q.id,
        course_id=q.course_id,
        qtype=q.qtype,
        topic=q.topic,
        stem=q.stem,
        options=q.options or [],
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/courses", response_model=list[CourseOut])
def courses():
    """课程列表：只返回有已入库文档的课程（空课程不展示，与资料管理保持一致）。"""
    with get_session() as session:
        return [_to_course_out(c) for c in list_courses(session) if c.documents]


@app.post("/courses")
def create_course(name: str, description: str = ""):
    with get_session() as session:
        course = get_or_create_course(session, name, description)
        session.commit()
        return _to_course_out(course)


@app.get("/documents", response_model=list[DocumentOut])
def documents():
    with get_session() as session:
        return [_to_document_out(d) for d in list_documents(session)]


@app.post("/documents", response_model=dict)
async def upload_document(
    file: UploadFile = File(...),
    course_name: str = Form("默认课程"),
):
    """上传文档并入库（multipart 表单）。"""
    max_upload_mb = get_settings().MAX_UPLOAD_MB
    max_upload_bytes = max_upload_mb * 1024 * 1024
    if file.size is not None and file.size > max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"上传文件不能超过 {max_upload_mb} MB",
        )
    content = await file.read(max_upload_bytes + 1)
    if len(content) > max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"上传文件不能超过 {max_upload_mb} MB",
        )
    try:
        result = ingest_file(file.filename or "unnamed", content, course_name)
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.delete("/documents/{document_id}")
def delete_doc(document_id: int):
    try:
        delete_document_consistently(
            document_id,
            resource_deleter=delete_document_file,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DocumentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DocumentDeletionError as exc:
        logger.exception("删除文档失败 document_id={}", document_id)
        raise HTTPException(
            status_code=503,
            detail="文档资源删除失败，已保留记录，可稍后重试。",
        ) from exc
    return {"deleted": document_id}


@app.post("/chat", response_model=dict)
def chat(req: ChatRequest):
    """Agent 对话接口：支持会话持久化与上下文压缩。"""
    try:
        with get_session() as session:
            result = run_chat(
                session,
                message=req.message,
                course_id=req.course_id,
                session_id=req.session_id,
                history=req.history,
            )
            session.commit()
        return result
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CourseNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SessionCourseConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat 调用失败")
        raise HTTPException(status_code=500, detail=f"对话失败：{exc}") from exc


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Agent 流式对话接口（SSE）：逐 token 返回回答，流结束后落库。

    事件格式（text/event-stream，每个 data 事件一个 JSON）：
    - {"type": "meta", "session_id": int}  —— 会话 ID（首条）
    - {"type": "token", "content": str}    —— 回答 token
    - {"type": "error", "message": str}    —— 流中途失败
    - {"type": "done"}                     —— 正常结束
    """
    if req.session_id is not None:
        with get_session() as session:
            chat_session = chat_repo.get_chat_session(session, req.session_id)
            if chat_session is None:
                raise HTTPException(status_code=404, detail="会话不存在")
            if (
                req.course_id is not None
                and req.course_id != chat_session.course_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail="会话课程范围与请求不一致，请新建会话后切换课程",
                )
    elif req.course_id is not None:
        with get_session() as session:
            _get_course_or_404(session, req.course_id)

    def event_stream():
        with get_session() as session:
            errored = False
            for event in run_chat_stream(
                session,
                message=req.message,
                course_id=req.course_id,
                session_id=req.session_id,
                history=req.history,
            ):
                if event.get("type") == "error":
                    errored = True
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if errored:
                session.rollback()
            else:
                session.commit()
                yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _chat_session_out(row: dict) -> ChatSessionOut:
    return ChatSessionOut(**row)


def _chat_message_out(m) -> ChatMessageOut:
    return ChatMessageOut(
        id=m.id, role=m.role, content=m.content, created_at=utc_isoformat(m.created_at)
    )


@app.get("/chat/sessions", response_model=list[ChatSessionOut])
def chat_sessions():
    """会话列表，按最后活动时间倒序。"""
    with get_session() as session:
        return [_chat_session_out(r) for r in chat_repo.list_chat_sessions(session)]


@app.post("/chat/sessions", response_model=ChatSessionOut)
def create_chat_session(req: CreateChatSessionRequest):
    """新建会话（可绑定课程范围）。"""
    with get_session() as session:
        if req.course_id is not None:
            _get_course_or_404(session, req.course_id)
        s = chat_repo.create_chat_session(session, course_id=req.course_id)
        session.commit()
        return _chat_session_out(
            {
                "id": s.id,
                "title": s.title,
                "course_id": s.course_id,
                "message_count": 0,
                "created_at": utc_isoformat(s.created_at),
                "updated_at": utc_isoformat(s.updated_at),
            }
        )


@app.delete("/chat/sessions/{session_id}")
def delete_chat_session_route(session_id: int):
    """删除会话（级联删除消息）。"""
    with get_session() as session:
        s = chat_repo.get_chat_session(session, session_id)
        if s is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        chat_repo.delete_chat_session(session, s)
        session.commit()
    return {"deleted": session_id}


@app.get("/chat/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def chat_messages(session_id: int):
    """读取某会话的全部消息（按时间升序）。"""
    with get_session() as session:
        s = chat_repo.get_chat_session(session, session_id)
        if s is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        return [
            _chat_message_out(m)
            for m in chat_repo.list_chat_messages(session, session_id)
        ]


@app.post("/questions/generate", response_model=list[QuestionPublicOut])
def generate(req: GenerateQuestionsRequest):
    """自动出题：调用 Agent 服务生成题目 → 持久化 → 返回带 ID 的题目列表。"""
    with get_session() as session:
        course = _get_course_or_404(session, req.course_id)
    try:
        qset = service.generate_questions(
            course_id=req.course_id,
            topic=req.topic,
            count=req.count,
            qtype=req.qtype,
        )
    except NoRelevantCourseMaterialError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("出题失败")
        raise HTTPException(status_code=500, detail=f"出题失败：{exc}") from exc
    payload = [q.model_dump() for q in qset.questions]
    with get_session() as session:
        ids = save_questions(session, req.course_id, payload)
        session.commit()
        questions = [get_question(session, qid) for qid in ids]
        return [_to_question_out(q) for q in questions if q is not None]


@app.post("/questions/{question_id}/grade", response_model=GradeOut)
def grade(question_id: int, req: GradeRequest):
    """批改作答：用题目相关上下文 + 参考答案做结构化批改，并记录作答。"""
    with get_session() as session:
        question = get_question(session, question_id)
        if question is None:
            raise HTTPException(status_code=404, detail="题目不存在")
        context = service.search_as_text(question.stem, course_id=question.course_id)
        result = service.grade_answer(
            question=question.stem,
            reference_answer=question.answer,
            user_answer=req.user_answer,
            context=context,
            options=question.options or [],
        )
        attempt = save_attempt(
            session,
            question_id=question_id,
            user_answer=req.user_answer,
            score=result.score,
            is_correct=result.is_correct,
            feedback=result.feedback,
        )
        session.commit()
    return {
        "attempt_id": attempt.id,
        "is_correct": result.is_correct,
        "score": result.score,
        "feedback": result.feedback,
        "knowledge_point": result.knowledge_point,
        "correct_answer": question.answer,
        "explanation": question.explanation,
    }


@app.get("/stats/mistakes")
def stats(
    course_id: int | None = None,
    qtype: str | None = None,
    topic: str | None = None,
):
    with get_session() as session:
        return mistake_stats(
            session, course_id=course_id, qtype=qtype, topic=topic
        )


def _get_course_or_404(session, course_id: int):
    from coursemate.db.repo import get_course

    course = get_course(session, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    return course
