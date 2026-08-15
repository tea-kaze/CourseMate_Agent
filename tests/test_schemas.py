from __future__ import annotations

import pytest
from pydantic import ValidationError

from coursemate.agent.schemas import GradeResult, QuestionSet


def test_question_set_valid():
    qs = QuestionSet.model_validate(
        {
            "questions": [
                {
                    "qtype": "single",
                    "stem": "1+1=?",
                    "options": ["2", "3"],
                    "answer": "2",
                }
            ]
        }
    )
    assert qs.questions[0].qtype == "single"


def test_grade_result_score_bounds():
    with pytest.raises(ValidationError):
        GradeResult(is_correct=True, score=101, feedback="越界")


def test_grade_result_short_answer_ok():
    r = GradeResult(is_correct=False, score=40, feedback="要点缺失", knowledge_point="进程")
    assert r.knowledge_point == "进程"
