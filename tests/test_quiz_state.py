"""刷题答案解析的行为测试。

点名要抓住的破坏：多选题选项文本自身含「、」（顿号）时，
按「、」切分会把选项切碎，导致用户所选选项（如 D）无法被识别。
"""

from __future__ import annotations

from coursemate.web.quiz_state import correct_options, selected_options


OS_OPTIONS = [
    "A. 进程是程序的一次执行过程，是操作系统进行资源分配和调度的基本单位",
    "B. 进程控制块（PCB）是进程存在的唯一标志，记录了进程标识符、状态、优先级等信息",
    "C. 短作业优先（SJF）算法需要预知作业的运行时间，且可能导致长作业饿死",
    "D. 死锁产生的四个必要条件包括互斥、占有并等待、可剥夺和循环等待",
    "E. 多级反馈队列调度算法中，新进程进入最高优先级队列，时间片用尽后降级",
    "F. 先来先服务（FCFS）算法可能产生护航效应，即短作业等待长作业",
]


def test_selected_options_recognizes_letters_with_inner_enumerating_commas():
    """提交选项字母（A、B、C、D、F）时，含顿号的选项 B/D 必须被识别。"""
    result = selected_options("A、B、C、D、F", OS_OPTIONS)
    assert result == {
        OS_OPTIONS[0],
        OS_OPTIONS[1],
        OS_OPTIONS[2],
        OS_OPTIONS[3],
        OS_OPTIONS[5],
    }, "含顿号的选项未被识别"


def test_selected_options_recognizes_legacy_full_text_answers():
    """兼容旧数据：完整选项文本用「、」连接时，含顿号的选项也能恢复。"""
    user_answer = "、".join(
        [OS_OPTIONS[0], OS_OPTIONS[1], OS_OPTIONS[2], OS_OPTIONS[3], OS_OPTIONS[5]]
    )
    result = selected_options(user_answer, OS_OPTIONS)
    assert result == {
        OS_OPTIONS[0],
        OS_OPTIONS[1],
        OS_OPTIONS[2],
        OS_OPTIONS[3],
        OS_OPTIONS[5],
    }


def test_selected_options_recognizes_newline_joined_full_texts():
    """换行连接的完整选项文本也应正常解析。"""
    user_answer = "\n".join([OS_OPTIONS[1], OS_OPTIONS[3]])
    result = selected_options(user_answer, OS_OPTIONS)
    assert result == {OS_OPTIONS[1], OS_OPTIONS[3]}


def test_correct_options_maps_letters_to_option_texts():
    """参考答案为字母（A、B、C、E、F）时，映射回完整选项文本用于标识。"""
    result = correct_options("A、B、C、E、F", OS_OPTIONS)
    assert result == {
        OS_OPTIONS[0],
        OS_OPTIONS[1],
        OS_OPTIONS[2],
        OS_OPTIONS[4],
        OS_OPTIONS[5],
    }


def test_correct_options_accepts_full_text_answers():
    """参考答案为完整选项文本时同样可用。"""
    result = correct_options("、".join([OS_OPTIONS[0], OS_OPTIONS[1]]), OS_OPTIONS)
    assert result == {OS_OPTIONS[0], OS_OPTIONS[1]}
