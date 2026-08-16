from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from coursemate.agent.schemas import GradeResult
from coursemate.app import main
from coursemate.app.schemas import GenerateQuestionsRequest, GradeRequest
from coursemate.app.schemas import CreateChatSessionRequest
from coursemate.db import repo


def test_question_public_response_does_not_expose_answer():
    question = SimpleNamespace(
        id=1,
        course_id=2,
        qtype="single",
        topic="进程",
        stem="时间片轮转属于哪种调度？",
        options=["A. 抢占式", "B. 非抢占式"],
        answer="A. 抢占式",
        explanation="按时间片抢占 CPU。",
    )

    result = main._to_question_out(question)

    assert result.model_dump() == {
        "id": 1,
        "course_id": 2,
        "qtype": "single",
        "topic": "进程",
        "stem": "时间片轮转属于哪种调度？",
        "options": ["A. 抢占式", "B. 非抢占式"],
    }


def test_grade_request_rejects_duplicate_question_id():
    assert GradeRequest(user_answer="A").user_answer == "A"
    with pytest.raises(ValidationError):
        GradeRequest.model_validate({"question_id": 1, "user_answer": "A"})


def test_grade_response_reveals_explanation_only_after_grading(
    monkeypatch, postgres_session_factory
):
    Session = postgres_session_factory
    with Session() as session:
        course = repo.get_or_create_course(session, "操作系统")
        question_id = repo.save_questions(
            session,
            course.id,
            [
                {
                    "qtype": "single",
                    "topic": "进程",
                    "stem": "时间片轮转属于哪种调度？",
                    "options": ["A. 抢占式", "B. 非抢占式"],
                    "answer": "A. 抢占式",
                    "explanation": "时间片耗尽后抢占并切换。",
                }
            ],
        )[0]
        session.commit()

    monkeypatch.setattr(main, "get_session", Session)
    main.service = SimpleNamespace(
        search_as_text=lambda *args, **kwargs: "context",
        grade_answer=lambda **kwargs: GradeResult(
            is_correct=True,
            score=100,
            feedback="正确",
            knowledge_point="进程",
        ),
    )

    result = main.grade(question_id, GradeRequest(user_answer="A. 抢占式"))

    assert result["correct_answer"] == "A. 抢占式"
    assert result["explanation"] == "时间片耗尽后抢占并切换。"


def test_create_chat_session_rejects_missing_course(
    monkeypatch, postgres_session_factory
):
    Session = postgres_session_factory
    monkeypatch.setattr(main, "get_session", Session)

    with pytest.raises(HTTPException) as exc_info:
        main.create_chat_session(CreateChatSessionRequest(course_id=999))

    assert exc_info.value.status_code == 404


def test_generate_questions_returns_conflict_for_empty_knowledge_base(
    monkeypatch, postgres_session_factory
):
    Session = postgres_session_factory
    with Session() as session:
        course = repo.get_or_create_course(session, "empty course")
        course_id = course.id
        session.commit()

    def reject_empty_course(**kwargs):
        from coursemate.agent.service import NoRelevantCourseMaterialError

        raise NoRelevantCourseMaterialError()

    monkeypatch.setattr(main, "get_session", Session)
    monkeypatch.setattr(
        main,
        "service",
        SimpleNamespace(generate_questions=reject_empty_course),
    )

    with pytest.raises(HTTPException) as exc_info:
        main.generate(
            GenerateQuestionsRequest(
                course_id=course_id,
                topic="process",
                count=1,
                qtype="single",
            )
        )

    assert exc_info.value.status_code == 409
    assert "课程资料" in exc_info.value.detail
