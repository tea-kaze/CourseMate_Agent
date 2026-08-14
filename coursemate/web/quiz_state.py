"""刷题练习的批改状态管理。

Streamlit 每次交互都会整页重跑，因此"已批改"状态必须持久化到
session_state 中；本模块集中管理这些状态键与读写逻辑，供页面渲染使用。
"""

from __future__ import annotations

from typing import Any


def grade_result_key(question_id: int) -> str:
    """返回某道题批改结果在 session_state 中的键名。"""
    return f"grade_result_{question_id}"


def is_graded(question_id: int, session_state: Any) -> bool:
    """判断该题是否已完成批改（决定是否隐藏作答控件）。"""
    return grade_result_key(question_id) in session_state


def get_grade_result(question_id: int, session_state: Any) -> dict | None:
    """读取该题的批改结果，未批改时返回 None。"""
    return session_state.get(grade_result_key(question_id))


def mark_graded(question_id: int, result: dict, session_state: Any) -> None:
    """批改完成后保存结果，保证页面重绘后反馈仍显示。"""
    session_state[grade_result_key(question_id)] = result


def _split_answer(answer: str) -> list[str]:
    """把提交的答案切成条目：多选题用「、」连接选项字母，兼容换行连接。"""
    if not answer:
        return []
    text = answer.replace("\n", "、")
    return [p.strip() for p in text.split("、") if p.strip()]


def _extract_letter(text: str) -> str | None:
    """提取条目开头的选项字母（如 "B."、"B、"、"B "），无字母前缀返回 None。"""
    s = text.strip()
    if not s or not s[0].isalpha():
        return None
    rest = s[1:2]
    if rest in ("", ".", "、", ":", "：", " "):
        return s[0].upper()
    return None


def _match_options(parts: list[str], options: list[str]) -> set[str]:
    """把解析出的条目映射为选项集合（返回完整选项文本）。

    匹配顺序：完整文本精确匹配 → 选项字母（A/B/C…，按选项顺序对应）→
    旧数据中被「、」切碎的片段回退（按开头字母或前缀匹配）。
    """
    letter_map: dict[str, str] = {}
    for i, opt in enumerate(options):
        letter = _extract_letter(opt) or chr(ord("A") + i)
        letter_map.setdefault(letter, opt)

    matched: set[str] = set()
    for part in parts:
        if part in options:
            matched.add(part)
            continue
        letter = _extract_letter(part)
        if letter and letter in letter_map:
            matched.add(letter_map[letter])
            continue
        for opt in options:
            if opt.startswith(part):
                matched.add(opt)
                break
    return matched


def selected_options(user_answer: str, options: list[str]) -> set[str]:
    """把提交的答案文本解析为用户勾选的选项集合。

    多选题提交选项字母（A、B、C…）；单选题提交单个选项文本；
    同时兼容旧数据中「用顿号连接完整选项文本」的格式。
    """
    return _match_options(_split_answer(user_answer), options)


def correct_options(answer: str, options: list[str]) -> set[str]:
    """从参考答案中解析出正确选项集合，用于批改后的正确标识。"""
    return _match_options(_split_answer(answer), options)


def clear_old_results(question_ids: list[int], session_state: Any) -> None:
    """生成新题组时清理旧题目的批改状态，避免新旧题目状态串扰。"""
    for qid in question_ids:
        session_state.pop(grade_result_key(qid), None)
