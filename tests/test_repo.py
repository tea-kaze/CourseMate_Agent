from __future__ import annotations

from coursemate.db import repo


def test_get_or_create_course(fresh_db):
    course = repo.get_or_create_course(fresh_db, "操作系统")
    same = repo.get_or_create_course(fresh_db, "操作系统")
    assert course.id == same.id
    assert len(repo.list_courses(fresh_db)) == 1


def test_document_crud(fresh_db):
    course = repo.get_or_create_course(fresh_db, "计算机网络")
    doc = repo.create_document(
        fresh_db, course.id, "ch1.md", "/tmp/ch1.md", "md", 12
    )
    assert repo.get_document(fresh_db, doc.id).filename == "ch1.md"
    assert repo.get_course_index(fresh_db)[0]["document_count"] == 1
    repo.delete_document(fresh_db, doc)
    assert repo.list_documents(fresh_db) == []


def test_question_and_attempt_flow(fresh_db):
    course = repo.get_or_create_course(fresh_db, "数据库原理")
    ids = repo.save_questions(
        fresh_db,
        course.id,
        [
            {
                "qtype": "single",
                "topic": "索引",
                "stem": "B+ 树索引适合哪种查询？",
                "options": ["A. 等值", "B. 范围"],
                "answer": "B. 范围",
                "explanation": "B+ 树支持范围扫描。",
            }
        ],
    )
    q = repo.get_question(fresh_db, ids[0])
    repo.save_attempt(fresh_db, q.id, "A. 等值", 0, False, "答错了")
    stats = repo.mistake_stats(fresh_db, course.id)
    assert stats["total_attempts"] == 1
    assert stats["accuracy"] == 0
    assert len(stats["wrong_attempts"]) == 1
    assert stats["by_topic"]["索引"]["total"] == 1


def test_mistake_stats_accuracy(fresh_db):
    course = repo.get_or_create_course(fresh_db, "课程X")
    qid = repo.save_questions(
        fresh_db,
        course.id,
        [{"qtype": "short", "stem": "什么是死锁？", "answer": "……", "explanation": ""}],
    )[0]
    q = repo.get_question(fresh_db, qid)
    repo.save_attempt(fresh_db, q.id, "对", 90, True, "很好")
    repo.save_attempt(fresh_db, q.id, "错", 30, False, "再想想")
    stats = repo.mistake_stats(fresh_db)
    assert stats["correct_count"] == 1
    assert stats["accuracy"] == 0.5


def test_mistake_stats_wrong_attempts_include_options(fresh_db):
    """近期错题必须携带题目的完整选项，供错题本展示。"""
    course = repo.get_or_create_course(fresh_db, "错题本")
    qid = repo.save_questions(
        fresh_db,
        course.id,
        [
            {
                "qtype": "multiple",
                "topic": "进程调度",
                "stem": "以下哪些属于进程调度算法？",
                "options": ["A. FCFS", "B. SJF", "C. 时间片轮转"],
                "answer": "A. FCFS、B. SJF、C. 时间片轮转",
                "explanation": "三者均为调度算法。",
            }
        ],
    )[0]
    q = repo.get_question(fresh_db, qid)
    repo.save_attempt(fresh_db, q.id, "A. FCFS", 0, False, "答案错误")
    stats = repo.mistake_stats(fresh_db, course.id)
    wrong = stats["wrong_attempts"][0]
    assert wrong["options"] == ["A. FCFS", "B. SJF", "C. 时间片轮转"]


def test_mistake_stats_filter_wrong_attempts_by_qtype_and_topic(fresh_db):
    """qtype/topic 只过滤近期错题明细（50 条上限之前），聚合统计保持全量。"""
    course = repo.get_or_create_course(fresh_db, "错题筛选")
    q_single = repo.save_questions(
        fresh_db,
        course.id,
        [
            {
                "qtype": "single",
                "topic": "进程调度",
                "stem": "时间片轮转属于哪种调度方式？",
                "options": ["A. 抢占式", "B. 非抢占式"],
                "answer": "A. 抢占式",
                "explanation": "",
            }
        ],
    )[0]
    q_multi = repo.save_questions(
        fresh_db,
        course.id,
        [
            {
                "qtype": "multiple",
                "topic": "进程调度",
                "stem": "以下哪些属于进程调度算法？",
                "options": ["A. FCFS", "B. SJF"],
                "answer": "A. FCFS、B. SJF",
                "explanation": "",
            }
        ],
    )[0]
    q_short = repo.save_questions(
        fresh_db,
        course.id,
        [
            {
                "qtype": "short",
                "topic": "死锁",
                "stem": "什么是死锁？",
                "answer": "……",
                "explanation": "",
            }
        ],
    )[0]
    q_no_topic = repo.save_questions(
        fresh_db,
        course.id,
        [{"qtype": "short", "stem": "无知识点题目", "answer": "略", "explanation": ""}],
    )[0]
    repo.save_attempt(fresh_db, q_single, "B. 非抢占式", 0, False, "答错")
    repo.save_attempt(fresh_db, q_multi, "A. FCFS", 0, False, "答错")
    repo.save_attempt(fresh_db, q_short, "对", 90, True, "答对")
    repo.save_attempt(fresh_db, q_no_topic, "错", 0, False, "答错")

    all_stats = repo.mistake_stats(fresh_db, course.id)
    assert all_stats["total_attempts"] == 4
    assert len(all_stats["wrong_attempts"]) == 3

    by_type = repo.mistake_stats(fresh_db, course.id, qtype="single")
    assert [w["qtype"] for w in by_type["wrong_attempts"]] == ["single"]
    assert by_type["total_attempts"] == 4  # 聚合不受筛选影响

    by_topic = repo.mistake_stats(fresh_db, course.id, topic="进程调度")
    assert {w["qtype"] for w in by_topic["wrong_attempts"]} == {"single", "multiple"}
    assert by_topic["total_attempts"] == 4

    combined = repo.mistake_stats(
        fresh_db, course.id, qtype="multiple", topic="进程调度"
    )
    assert len(combined["wrong_attempts"]) == 1
    assert combined["wrong_attempts"][0]["qtype"] == "multiple"

    untagged = repo.mistake_stats(fresh_db, course.id, topic="未分类")
    assert [w["stem"] for w in untagged["wrong_attempts"]] == ["无知识点题目"]
