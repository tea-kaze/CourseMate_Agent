"""课程/文档/题目/作答记录的仓库函数。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from coursemate.db.models import (
    AnswerAttempt,
    Course,
    Document,
    DocumentStatus,
    Question,
)


# ---------- Course ----------
def get_or_create_course(session: Session, name: str, description: str = "") -> Course:
    course = session.scalar(select(Course).where(Course.name == name))
    if course is None:
        course = Course(name=name, description=description)
        session.add(course)
        session.flush()
    return course


def list_courses(session: Session) -> list[Course]:
    """只列出至少有一个可检索文档的课程，并只预加载 ready 文档。"""
    query = (
        select(Course)
        .where(Course.documents.any(Document.status == DocumentStatus.READY))
        .options(
            selectinload(
                Course.documents.and_(Document.status == DocumentStatus.READY)
            )
        )
        .order_by(Course.id)
    )
    return list(session.scalars(query))


def list_all_courses(session: Session) -> list[Course]:
    """列出所有课程，供清理和后台管理流程使用。"""
    return list(session.scalars(select(Course).order_by(Course.id)))


def get_course(session: Session, course_id: int) -> Course | None:
    return session.get(Course, course_id)


def get_course_index(session: Session) -> list[dict]:
    """返回课程及其文档数量，供 Agent 了解可用的知识范围。

    这是 get_course_index 工具的底层实现：模型先"看一眼"有哪些课程，
    再决定用哪个 course_id 检索，避免凭空猜测。
    空课程（无文档）不返回，避免列出无法检索的课程。
    """
    result: list[dict] = []
    for course in list_courses(session):
        docs = session.scalars(
            select(Document)
            .where(
                Document.course_id == course.id,
                Document.status == DocumentStatus.READY,
            )
            .order_by(Document.id)
        ).all()
        if not docs:
            continue
        result.append(
            {
                "course_id": course.id,
                "course_name": course.name,
                "document_count": len(docs),
                "documents": [d.filename for d in docs],
            }
        )
    return result


# ---------- Document ----------
def create_document(
    session: Session,
    course_id: int,
    filename: str,
    file_path: str,
    doc_type: str,
    chunk_count: int,
    status: DocumentStatus | str = DocumentStatus.PENDING,
) -> Document:
    doc = Document(
        course_id=course_id,
        filename=filename,
        file_path=file_path,
        doc_type=doc_type,
        chunk_count=chunk_count,
        status=DocumentStatus(status),
    )
    session.add(doc)
    session.flush()
    return doc


def list_documents(session: Session) -> list[Document]:
    return list(
        session.scalars(
            select(Document)
            .where(Document.status == DocumentStatus.READY)
            .options(joinedload(Document.course))
            .order_by(Document.id.desc())
        )
    )


def list_all_documents(session: Session) -> list[Document]:
    """列出所有状态的文档，供补偿和清理流程使用。"""
    return list(
        session.scalars(
            select(Document)
            .options(joinedload(Document.course))
            .order_by(Document.id.desc())
        )
    )


def update_document_status(
    session: Session,
    document: Document,
    status: DocumentStatus | str,
    *,
    chunk_count: int | None = None,
    last_error: str | None = None,
) -> Document:
    document.status = DocumentStatus(status)
    document.last_error = last_error
    if chunk_count is not None:
        document.chunk_count = chunk_count
    session.flush()
    return document


def list_stale_ingestions(session: Session, *, before: datetime) -> list[Document]:
    """列出超过截止时间仍未完成或入库失败的文档。"""
    return list(
        session.scalars(
            select(Document)
            .where(
                Document.status.in_(
                    [DocumentStatus.PENDING, DocumentStatus.INGEST_FAILED]
                ),
                Document.created_at < before,
            )
            .options(joinedload(Document.course))
            .order_by(Document.id)
        )
    )


def get_document(session: Session, document_id: int) -> Document | None:
    return session.get(Document, document_id)


def delete_document(session: Session, document: Document) -> None:
    session.delete(document)
    session.flush()


# ---------- Question ----------
def save_questions(session: Session, course_id: int, questions: list[dict]) -> list[int]:
    """批量保存题目，返回生成的题目 ID 列表（供前端跳转批改）。"""
    ids: list[int] = []
    for q in questions:
        question = Question(
            course_id=course_id,
            qtype=q["qtype"],
            topic=q.get("topic", ""),
            stem=q["stem"],
            options=q.get("options"),
            answer=q.get("answer", ""),
            explanation=q.get("explanation", ""),
        )
        session.add(question)
        session.flush()
        ids.append(question.id)
    return ids


def get_question(session: Session, question_id: int) -> Question | None:
    return session.get(Question, question_id)


def get_questions_by_course(session: Session, course_id: int) -> list[Question]:
    return list(
        session.scalars(
            select(Question).where(Question.course_id == course_id)
        )
    )


# ---------- Attempt ----------
def save_attempt(
    session: Session,
    question_id: int,
    user_answer: str,
    score: float,
    is_correct: bool,
    feedback: str,
) -> AnswerAttempt:
    attempt = AnswerAttempt(
        question_id=question_id,
        user_answer=user_answer,
        score=score,
        is_correct=is_correct,
        feedback=feedback,
    )
    session.add(attempt)
    session.flush()
    return attempt


def mistake_stats(
    session: Session,
    course_id: int | None = None,
    qtype: str | None = None,
    topic: str | None = None,
) -> dict:
    """错题统计：总数、正确率、按题型/知识点分布 + 近期错题明细。

    这是错题本页面的数据源；course_id 为空时统计全部课程。
    qtype/topic 只过滤近期错题明细（在 50 条上限之前生效），
    顶部聚合统计保持全量，不随筛选变化。
    """
    q = select(AnswerAttempt).join(Question)
    if course_id is not None:
        q = q.where(Question.course_id == course_id)
    attempts = list(session.scalars(q))
    total = len(attempts)
    correct = sum(1 for a in attempts if a.is_correct)
    by_type: dict[str, dict] = {}
    by_topic: dict[str, dict] = {}
    for a in attempts:
        attempt_qtype = a.question.qtype
        attempt_topic = a.question.topic or "未分类"
        for bucket, key in ((by_type, attempt_qtype), (by_topic, attempt_topic)):
            item = bucket.setdefault(key, {"total": 0, "correct": 0})
            item["total"] += 1
            if a.is_correct:
                item["correct"] += 1
    wrong_attempts = [
        {
            "attempt_id": a.id,
            "question_id": a.question_id,
            "stem": a.question.stem,
            "qtype": a.question.qtype,
            "topic": a.question.topic or "未分类",
            "options": a.question.options or [],
            "user_answer": a.user_answer,
            "correct_answer": a.question.answer,
            "feedback": a.feedback,
            "score": a.score,
            "created_at": a.created_at.isoformat(),
        }
        for a in attempts
        if not a.is_correct
        and (qtype is None or a.question.qtype == qtype)
        and (topic is None or (a.question.topic or "未分类") == topic)
    ]
    wrong_attempts.sort(key=lambda x: x["created_at"], reverse=True)
    return {
        "total_attempts": total,
        "correct_count": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "by_type": by_type,
        "by_topic": by_topic,
        "wrong_attempts": wrong_attempts[:50],
    }
