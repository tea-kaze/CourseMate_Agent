"""刷题练习页面的行为测试。

点名要抓住的破坏：
1. 批改后仍可重复作答（提交按钮不消失）；
2. 批改反馈不持久化，切换选项后消失；
3. 多选题只能单选（与题目语义不符）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from coursemate.web import api_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUIZ_PAGE = PROJECT_ROOT / "coursemate/web/pages/3_✍️_刷题练习.py"


COURSES = [{"id": 2, "name": "操作系统", "description": "", "document_count": 1}]

QUESTIONS = [
    {
        "id": 101,
        "course_id": 2,
        "qtype": "single",
        "topic": "进程调度",
        "stem": "时间片轮转属于哪种调度方式？",
        "options": ["A. 抢占式", "B. 非抢占式"],
    },
    {
        "id": 102,
        "course_id": 2,
        "qtype": "multiple",
        "topic": "进程调度",
        "stem": "以下哪些属于进程调度算法？",
        "options": ["A. FCFS", "B. SJF", "C. 时间片轮转"],
    },
]

GRADE_RESULT = {
    "attempt_id": 1,
    "is_correct": False,
    "score": 0,
    "feedback": "答案错误，请复习调度算法。",
    "knowledge_point": "进程调度",
    "correct_answer": "A. 抢占式",
}


@pytest.fixture()
def page(monkeypatch: pytest.MonkeyPatch):
    """替换外部 API 调用，其余页面逻辑保持真实。"""
    calls: dict[str, list] = {"grade": [], "generate": []}

    def fake_courses():
        return COURSES

    def fake_generate(course_id, topic, count, qtype):
        calls["generate"].append((course_id, topic, count, qtype))
        return QUESTIONS

    def fake_grade(question_id, user_answer):
        calls["grade"].append((question_id, user_answer))
        return GRADE_RESULT

    monkeypatch.setattr(api_client, "get_courses", fake_courses)
    monkeypatch.setattr(api_client, "generate_questions", fake_generate)
    monkeypatch.setattr(api_client, "grade", fake_grade)

    at = AppTest.from_file(
        str(QUIZ_PAGE), default_timeout=10
    )
    at.run()
    return at, calls


def test_generate_questions_shows_submit_buttons(page):
    """生成题目后每道题都有提交按钮。"""
    at, calls = page
    at.button[0].click().run()
    # 生成题目按钮 + 两道题的提交按钮
    assert len(at.button) == 3


def test_graded_question_keeps_feedback_and_hides_submit(page):
    """批改后：反馈保持显示（切换选项不消失），且提交按钮消失（不能重复作答）。"""
    at, calls = page
    at.button[0].click().run()  # 生成题目
    assert len(at.button) == 3

    at.button(key="grade_101").click().run()  # 提交第一题
    assert calls["grade"] == [(101, "A. 抢占式")]
    # 已批改：本题提交按钮应消失（st.rerun 立即重绘）
    assert len(at.button) == 2

    # 切换其他题目的控件 → 页面重跑，反馈必须仍在
    at.checkbox[0].set_value(True).run()  # 勾选第二题第一个选项触发重绘
    feedback_texts = [m.value for m in at.markdown]
    assert any("答案错误" in t for t in feedback_texts), (
        "切换选项后批改反馈消失"
    )
    assert len(at.button) == 2


def test_multiple_choice_accepts_multiple_selections(page):
    """多选题应允许多选，且提交时用选项字母合并传给批改接口。"""
    at, calls = page
    at.button[0].click().run()  # 生成题目
    # 第二题是多选题：选择两个选项后提交
    at.checkbox[1].set_value(True).run()  # B. SJF
    at.checkbox[2].set_value(True).run()  # C. 时间片轮转
    at.button(key="grade_102").click().run()
    assert calls["grade"][0][0] == 102
    assert calls["grade"][0][1] == "B、C", "多选题应按选项字母提交"


def test_multiple_choice_option_with_inner_enumerating_comma_is_recognized(
    monkeypatch: pytest.MonkeyPatch,
):
    """回归：选项文本含「、」时（如死锁必要条件），用户选择后必须被识别。"""
    questions = [
        {
            "id": 103,
            "course_id": 2,
            "qtype": "multiple",
            "topic": "死锁",
            "stem": "关于死锁的描述，正确的有？",
            "options": [
                "A. 死锁只发生在并发系统中",
                "B. 死锁产生的必要条件包括互斥、占有并等待、不可剥夺和循环等待",
                "C. 银行家算法用于避免死锁",
            ],
            "answer": "B、C",
            "explanation": "",
        }
    ]
    captured: dict = {}

    def fake_courses():
        return COURSES

    def fake_generate(course_id, topic, count, qtype):
        return questions

    def fake_grade(question_id, user_answer):
        captured["answer"] = user_answer
        return {**GRADE_RESULT, "correct_answer": "B、C"}

    monkeypatch.setattr(api_client, "get_courses", fake_courses)
    monkeypatch.setattr(api_client, "generate_questions", fake_generate)
    monkeypatch.setattr(api_client, "grade", fake_grade)

    at = AppTest.from_file(str(QUIZ_PAGE), default_timeout=10)
    at.run()
    at.button[0].click().run()  # 生成题目
    at.checkbox[1].set_value(True).run()  # B（含顿号）
    at.checkbox[2].set_value(True).run()  # C
    at.button(key="grade_103").click().run()
    assert captured["answer"] == "B、C"
    md_texts = [m.value for m in at.markdown]
    marked = [t for t in md_texts if "我的答案" in t]
    assert any("互斥、占有并等待、不可剥夺和循环等待" in t for t in marked), (
        "含顿号的选项未被标识为我的答案"
    )
    assert any("**你的答案**：B、C" in t for t in md_texts), "你的答案行显示异常"


def test_graded_question_keeps_options_and_marks_user_selection(page):
    """批改后：保留原题全部选项，并标识用户所选答案与正确答案。"""
    at, calls = page
    at.button[0].click().run()  # 生成题目
    at.button(key="grade_101").click().run()  # 提交单选第一题（默认选 A）

    # 已批改分支仍展示两个选项
    option_marks = [m.value for m in at.markdown if m.value.startswith("- ")]
    assert any("A. 抢占式" in t for t in option_marks), "已批改后选项消失"
    assert any("B. 非抢占式" in t for t in option_marks)
    # 用户所选（A）有"我的答案"标识，且正确答案也有标识
    md_texts = [m.value for m in at.markdown]
    assert any("我的答案" in t for t in md_texts)
    # 「你的答案」与「正确答案」按顺序出现在得分与反馈之间
    assert any("**你的答案**：A. 抢占式" in t for t in md_texts), "缺少你的答案行"
    assert any("**正确答案**：A. 抢占式" in t for t in md_texts), "缺少正确答案行"
    score_idx = next(i for i, t in enumerate(md_texts) if "得分" in t)
    answer_idx = next(i for i, t in enumerate(md_texts) if t.startswith("**你的答案**"))
    correct_idx = next(i for i, t in enumerate(md_texts) if t.startswith("**正确答案**"))
    feedback_idx = next(i for i, t in enumerate(md_texts) if "**反馈**" in t)
    assert score_idx < answer_idx < correct_idx < feedback_idx, (
        "你的答案/正确答案未按预期位于得分与反馈之间"
    )

    # 第二题（多选题）已批改：两个所选选项都被标识
    at.checkbox[1].set_value(True).run()  # B. SJF
    at.checkbox[2].set_value(True).run()  # C. 时间片轮转
    at.button(key="grade_102").click().run()
    graded_marks = [m.value for m in at.markdown if "我的答案" in m.value]
    assert len(graded_marks) >= 1
    assert any("B. SJF" in m for m in graded_marks), "多选题已选项 B 未标识"
    assert any("C. 时间片轮转" in m for m in graded_marks), "多选题已选项 C 未标识"


def test_multiple_choice_uses_checkboxes_not_multiselect(page):
    """多选题使用勾选式组件（checkbox），而不是下拉式 multiselect。"""
    at, calls = page
    at.button[0].click().run()  # 生成题目
    # 第二题有 3 个选项 → 至少 3 个 checkbox
    assert len(at.checkbox) >= 3
    assert len(at.multiselect) == 0
