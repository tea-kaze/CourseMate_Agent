"""错题本页面的行为测试。

点名要抓住的破坏：近期错题只显示题干、用户答案与反馈，
缺少题目的完整选项、正确答案标识。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from coursemate.web import api_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MISTAKE_PAGE = PROJECT_ROOT / "coursemate/web/pages/4_📒_错题本.py"


COURSES = [{"id": 2, "name": "操作系统", "description": "", "document_count": 1}]

STATS = {
    "total_attempts": 2,
    "correct_count": 0,
    "accuracy": 0.0,
    "by_type": {
        "single": {"total": 1, "correct": 0},
        "multiple": {"total": 1, "correct": 0},
    },
    "by_topic": {
        "进程调度": {"total": 2, "correct": 0},
    },
    "wrong_attempts": [
        {
            "attempt_id": 2,
            "question_id": 102,
            "stem": "以下哪些属于进程调度算法？",
            "qtype": "multiple",
            "topic": "进程调度",
            "options": ["A. FCFS", "B. SJF", "C. 时间片轮转"],
            "user_answer": "B. SJF、C. 时间片轮转",
            "correct_answer": "A. FCFS、B. SJF、C. 时间片轮转",
            "feedback": "答案不完整，请复习调度算法。",
            "score": 30,
            "created_at": "2026-08-14T00:01:00",
        },
        {
            "attempt_id": 1,
            "question_id": 101,
            "stem": "时间片轮转属于哪种调度方式？",
            "qtype": "single",
            "topic": "进程调度",
            "options": ["A. 抢占式", "B. 非抢占式"],
            "user_answer": "B. 非抢占式",
            "correct_answer": "A. 抢占式",
            "feedback": "答案错误，请复习调度算法。",
            "score": 0,
            "created_at": "2026-08-14T00:00:00",
        },
    ],
}


@pytest.fixture()
def page(monkeypatch: pytest.MonkeyPatch):
    """替换外部 API 调用，其余页面逻辑保持真实。"""

    def fake_courses():
        return COURSES

    def fake_mistake_stats(course_id=None):
        return STATS

    monkeypatch.setattr(api_client, "get_courses", fake_courses)
    monkeypatch.setattr(api_client, "mistake_stats", fake_mistake_stats)

    at = AppTest.from_file(str(MISTAKE_PAGE), default_timeout=10)
    at.run()
    return at


def test_wrong_book_shows_complete_question_with_options(page):
    """近期错题应展示题干、完整选项、用户答案、正确答案与反馈。"""
    at = page
    md_texts = [m.value for m in at.markdown]

    # 题干
    assert any("时间片轮转属于哪种调度方式" in t for t in md_texts)
    # 完整选项
    assert any("- A. 抢占式" in t for t in md_texts), "缺少选项 A"
    assert any("- B. 非抢占式" in t for t in md_texts), "缺少选项 B"
    # 用户答案 / 正确答案 / 反馈
    assert any("**你的答案**：B. 非抢占式" in t for t in md_texts), "缺少你的答案行"
    assert any("**正确答案**：A. 抢占式" in t for t in md_texts), "缺少正确答案行"
    assert any("答案错误" in t for t in md_texts), "缺少反馈信息"


def test_wrong_book_marks_user_selection_on_multiple_choice(page):
    """多选题的近期错题应标识用户所选答案与正确答案。"""
    at = page
    md_texts = [m.value for m in at.markdown]

    assert any("以下哪些属于进程调度算法" in t for t in md_texts)
    # 用户所选两个选项都被标识为「我的答案」
    user_marked = [t for t in md_texts if "我的答案" in t]
    assert any("B. SJF" in t for t in user_marked), "用户所选 B 未标识"
    assert any("C. 时间片轮转" in t for t in user_marked), "用户所选 C 未标识"
    # 正确答案三个选项都被标识
    correct_marked = [t for t in md_texts if "正确答案" in t]
    assert any("A. FCFS" in t for t in correct_marked), "正确选项 A 未标识"
    assert any("**正确答案**：A. FCFS、B. SJF、C. 时间片轮转" in t for t in correct_marked)
