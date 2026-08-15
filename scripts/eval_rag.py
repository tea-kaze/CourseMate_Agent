"""RAG 检索质量评估脚本。

用法：
1. 先导入演示资料（若课程未入库）：
       uv run python scripts/seed_demo.py
2. 运行检索评估（确定性，不需要 LLM）：
       uv run python scripts/eval_rag.py
3. 额外跑忠实度评估（LLM-as-judge，较慢）：
       uv run python scripts/eval_rag.py --faithfulness

检索评估输出每个问题的关键词覆盖率（课程内检索）与文档命中（全局检索）；
忠实度评估输出回答是否忠于上下文（有无编造）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from coursemate.agent.service import get_service  # noqa: E402
from coursemate.db.session import init_db  # noqa: E402
from coursemate.evaluation import load_golden_set, run_eval  # noqa: E402


def _resolve_documents(service) -> tuple[dict[str, int], list[str], Console]:
    """文档名 -> course_id 映射，以及 golden set 中未入库的文档列表。"""
    doc_to_course: dict[str, int] = {}
    for c in service.course_index():
        for doc in c["documents"]:
            doc_to_course[doc] = c["course_id"]
    return doc_to_course


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 检索质量评估")
    parser.add_argument(
        "--faithfulness", action="store_true", help="额外跑 LLM 忠实度评估（较慢）"
    )
    args = parser.parse_args()

    init_db()
    service = get_service()
    golden = load_golden_set()
    console = Console()

    # 文档名 -> course_id：课程名可能因上传方式而异，按文档名解析更稳
    doc_to_course = _resolve_documents(service)
    missing = sorted(
        {
            item["expected_document"]
            for item in golden
            if item["expected_document"] not in doc_to_course
        }
    )
    if missing:
        console.print("[red]以下文档未入库：[/red]" + "、".join(missing))
        console.print("请先运行 [bold]uv run python scripts/seed_demo.py[/bold] 导入演示资料。")
        sys.exit(1)

    course_id_for_document = lambda doc: doc_to_course.get(doc)  # noqa: E731

    report = run_eval(
        golden,
        search=service.search,
        course_id_for_document=course_id_for_document,
        top_k=5,
    )

    table = Table(title="RAG 检索评估结果", show_lines=True)
    table.add_column("ID", style="dim", width=8)
    table.add_column("问题", width=30)
    table.add_column("关键词覆盖率", justify="right", width=12)
    table.add_column("文档命中", justify="center", width=10)
    table.add_column("全局 top-5 文档", width=34)
    for it in report["items"]:
        table.add_row(
            it["id"],
            it["question"],
            f"{it['keyword_coverage']:.2%}",
            "✓" if it["document_hit"] else "✗",
            "、".join(it["global_top_docs"][:3]),
        )

    console.print(table)
    console.print(
        f"平均关键词覆盖率：[bold]{report['avg_keyword_coverage']:.2%}[/bold]   "
        f"全局文档命中率：[bold]{report['document_hit_rate']:.2%}[/bold]   "
        f"（共 {report['total']} 题）"
    )

    if args.faithfulness:
        from coursemate.agent.llm import get_llm
        from coursemate.evaluation import run_faithfulness_eval

        console.print("\n[bold]正在跑忠实度评估（LLM-as-judge，较慢）…[/bold]")
        llm = get_llm(temperature=0.0, thinking=False)
        f_report = run_faithfulness_eval(
            golden,
            search=service.search,
            course_id_for_document=course_id_for_document,
            llm=llm,
            top_k=5,
        )

        ftable = Table(title="忠实度评估结果（LLM-as-judge）", show_lines=True)
        ftable.add_column("ID", style="dim", width=8)
        ftable.add_column("问题", width=30)
        ftable.add_column("忠实度", justify="right", width=10)
        ftable.add_column("理由", width=44)
        for it in f_report["items"]:
            ftable.add_row(
                it["id"], it["question"], f"{it['faithfulness']:.2f}", it["rationale"]
            )

        console.print(ftable)
        console.print(
            f"平均忠实度：[bold]{f_report['avg_faithfulness']:.2%}[/bold]"
            f"（共 {f_report['total']} 题）"
        )


if __name__ == "__main__":
    main()
