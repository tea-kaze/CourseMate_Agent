"""LLM 客户端与结构化输出调用的行为测试。

点名要抓住的破坏：DeepSeek V4 思考模式不接受 tool_choice，
导致出题/批改的结构化输出调用被 API 以 400 拒绝。
"""

from __future__ import annotations

import pytest

from coursemate.agent import service as service_module
from coursemate.agent import llm as llm_module
from coursemate.agent.llm import get_llm
from coursemate.agent.schemas import GradeResult, QuestionItem, QuestionSet


class FakeSettings:
    LLM_MODEL = "deepseek-v4-flash"
    DEEPSEEK_API_KEY = "test-key"
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"


@pytest.fixture()
def fake_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(llm_module, "get_settings", lambda: FakeSettings())


def test_get_llm_disables_thinking_mode_when_requested(fake_settings):
    """结构化输出必须关闭思考模式，否则 tool_choice 会被 API 拒绝。"""
    llm = get_llm(temperature=0.4, thinking=False)
    assert llm.extra_body == {"thinking": {"type": "disabled"}}


def test_get_llm_keeps_thinking_mode_by_default(fake_settings):
    """普通调用（如对话 Agent）保持默认思考模式。"""
    llm = get_llm()
    assert llm.extra_body is None


def test_generate_questions_builds_llm_with_thinking_disabled(monkeypatch):
    """出题走结构化输出时，构造的 LLM 必须关闭思考模式。"""
    calls: dict = {}

    class FakeLLM:
        def with_structured_output(self, schema):
            assert schema is QuestionSet
            return self

        def invoke(self, prompt):
            return QuestionSet(
                questions=[
                    QuestionItem(
                        qtype="single",
                        stem="测试题",
                        options=["A", "B"],
                        answer="A",
                    )
                ]
            )

    def fake_get_llm(**kwargs):
        calls.update(kwargs)
        return FakeLLM()

    monkeypatch.setattr(service_module, "get_llm", fake_get_llm)
    svc = service_module.CourseMateService()
    monkeypatch.setattr(svc, "_course_name", lambda course_id: "测试课程")
    monkeypatch.setattr(svc, "search_as_text", lambda *args, **kwargs: "资料内容")

    result = svc.generate_questions(course_id=1, topic="进程", count=1, qtype="single")
    assert len(result.questions) == 1
    assert calls.get("thinking") is False, "出题未关闭思考模式"


def test_grade_answer_builds_llm_with_thinking_disabled(monkeypatch):
    """批改走结构化输出时，构造的 LLM 必须关闭思考模式。"""
    calls: dict = {}

    class FakeLLM:
        def with_structured_output(self, schema):
            assert schema is GradeResult
            return self

        def invoke(self, prompt):
            return GradeResult(is_correct=True, score=100, feedback="正确")

    def fake_get_llm(**kwargs):
        calls.update(kwargs)
        return FakeLLM()

    monkeypatch.setattr(service_module, "get_llm", fake_get_llm)
    svc = service_module.CourseMateService()

    result = svc.grade_answer(
        question="1+1=?", reference_answer="2", user_answer="2"
    )
    assert result.is_correct
    assert calls.get("thinking") is False, "批改未关闭思考模式"


def test_grade_answer_passes_options_so_llm_can_identify_selection(monkeypatch):
    """批改提示词必须包含选项文本，否则 LLM 无法识别学生所选（尤其含顿号的选项）。"""
    captured: dict = {}

    class FakeLLM:
        def with_structured_output(self, schema):
            assert schema is GradeResult
            return self

        def invoke(self, prompt):
            captured["prompt"] = prompt
            return GradeResult(is_correct=False, score=80, feedback="反馈")

    monkeypatch.setattr(service_module, "get_llm", lambda **kwargs: FakeLLM())
    svc = service_module.CourseMateService()
    options = [
        "A. 进程是程序的一次执行过程",
        "B. 死锁必要条件包括互斥、占有并等待、不可剥夺和循环等待",
    ]
    svc.grade_answer(
        question="关于进程与死锁，正确的有？",
        reference_answer="A、B",
        user_answer="A、B",
        options=options,
    )
    prompt = captured["prompt"]
    assert "死锁必要条件包括互斥、占有并等待、不可剥夺和循环等待" in prompt
    assert "学生作答：A、B" in prompt
