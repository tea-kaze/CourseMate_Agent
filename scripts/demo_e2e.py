"""端到端验证：入库 → 问答 → 出题 → 批改 → 错题统计。"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from coursemate.app.ingestion import ingest_file  # noqa: E402
from coursemate.agent.service import get_service  # noqa: E402
from coursemate.db.repo import get_question, save_attempt  # noqa: E402
from coursemate.db.session import get_session, init_db  # noqa: E402


def main() -> None:
    init_db()
    service = get_service()
    demo = ROOT / "data" / "demo" / "操作系统-进程与调度.md"
    if not demo.exists():
        print("未找到演示资料，请先创建 data/demo/操作系统-进程与调度.md")
        return

    print("== 1. 入库演示资料 ==")
    result = ingest_file(demo.name, demo.read_bytes(), course_name="操作系统")
    print(result)
    course_id = result["course_id"]

    print("\n== 2. 检索测试 ==")
    text = service.search_as_text("什么是时间片轮转调度？", course_id=course_id, top_k=3)
    print(text[:600])

    print("\n== 3. 生成题目 ==")
    qset = service.generate_questions(course_id, topic="进程调度", count=3, qtype="mixed")
    payload = [q.model_dump() for q in qset.questions]
    print([{ "qtype": q["qtype"], "stem": q["stem"][:40] } for q in payload])

    from coursemate.db.repo import save_questions

    with get_session() as session:
        ids = save_questions(session, course_id, payload)
        session.commit()
        q = get_question(session, ids[0])
        print("\n== 4. 批改第一题 ==")
        grade = service.grade_answer(
            question=q.stem,
            reference_answer=q.answer,
            user_answer="我不确定答案",
            context=service.search_as_text(q.stem, course_id=course_id, top_k=3),
        )
        print(grade.model_dump())
        save_attempt(
            session,
            question_id=q.id,
            user_answer="我不确定答案",
            score=grade.score,
            is_correct=grade.is_correct,
            feedback=grade.feedback,
        )
        session.commit()

    print("\n== 5. 错题统计 ==")
    from coursemate.db.repo import mistake_stats

    with get_session() as session:
        stats = mistake_stats(session, course_id=course_id)
    print({k: v for k, v in stats.items() if k != "wrong_attempts"})

    print("\n端到端验证完成 ✅")


if __name__ == "__main__":
    main()
