"""RAG 检索质量评估。

两个确定性指标（不需要 LLM、不引入额外依赖）：
1. 关键词覆盖率（keyword coverage）：带课程过滤检索 top-k，看期望答案的关键词被召回的比例；
2. 文档命中率（document hit rate）：不带课程过滤全局检索 top-k，看正确课程的文档是否进 top-k。

golden set 见 data/eval/golden_set.json，运行入口见 scripts/eval_rag.py。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

DEFAULT_GOLDEN_SET = (
    Path(__file__).resolve().parents[1] / "data" / "eval" / "golden_set.json"
)


def load_golden_set(path: str | Path = DEFAULT_GOLDEN_SET) -> list[dict]:
    """加载 golden set（问题 + 期望文档 + 期望关键词 + 参考要点）。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def documents_hit_document(docs: list[Any], expected_document: str) -> bool:
    """检索结果中是否命中期望文档（按 filename/source 匹配）。"""
    for doc in docs:
        md = doc.metadata or {}
        if md.get("filename") == expected_document or md.get("source") == expected_document:
            return True
    return False


def keyword_coverage(text: str, keywords: list[str]) -> float:
    """关键词覆盖率：出现在检索文本中的期望关键词占比（0.0~1.0）。"""
    if not keywords:
        return 1.0
    return sum(1 for kw in keywords if kw in text) / len(keywords)


def run_eval(
    golden: list[dict],
    *,
    search: Callable[..., list[Any]],
    course_id_for_document: Callable[[str], int | None],
    top_k: int = 5,
) -> dict:
    """对每个问题跑两轮检索并打分。

    search(query, course_id=None, top_k=top_k) -> list[Document]：
        带 course_id 为课程内检索，否则为全局检索。
    course_id_for_document(document_filename) -> course_id 或 None。
    （按文档名解析课程，避免依赖易变的课程名）

    返回 {total, avg_keyword_coverage, document_hit_rate, items}。
    """
    items: list[dict] = []
    kw_sum = 0.0
    doc_hits = 0

    for item in golden:
        question = item["question"]
        expected_doc = item["expected_document"]
        course_id = course_id_for_document(expected_doc)
        keywords = item.get("expected_keywords", [])

        # 1) 课程内检索：关键词覆盖率
        docs_scoped = search(question, course_id=course_id, top_k=top_k)
        scoped_text = "\n".join(d.page_content for d in docs_scoped)
        kw = keyword_coverage(scoped_text, keywords)
        kw_sum += kw

        # 2) 全局检索：正确文档是否进 top-k
        docs_global = search(question, course_id=None, top_k=top_k)
        hit = documents_hit_document(docs_global, expected_doc)
        doc_hits += 1 if hit else 0

        items.append(
            {
                "id": item["id"],
                "question": question,
                "keyword_coverage": round(kw, 3),
                "document_hit": hit,
                "global_top_docs": _unique_doc_names(docs_global),
            }
        )

    n = len(items)
    return {
        "total": n,
        "avg_keyword_coverage": round(kw_sum / n, 3) if n else 0.0,
        "document_hit_rate": round(doc_hits / n, 3) if n else 0.0,
        "items": items,
    }


def _unique_doc_names(docs: list[Any]) -> list[str]:
    """按顺序去重，返回检索文档的 filename（用于报告展示）。"""
    seen: list[str] = []
    for d in docs:
        md = d.metadata or {}
        name = md.get("filename") or md.get("source") or "?"
        if name not in seen:
            seen.append(name)
    return seen


class FaithfulnessVerdict(BaseModel):
    """LLM-as-judge 的忠实度判分结果。"""

    score: float = Field(ge=0, le=1, description="忠实度 0-1：1=完全有依据无编造，0=大量编造")
    rationale: str = Field(description="判断理由")


def generate_answer_from_context(question: str, context: str, llm: Any) -> str:
    """只用检索到的上下文回答问题（忠实度评估的生成步骤）。"""
    prompt = (
        "请仅根据以下上下文回答问题，不要使用外部知识；"
        "上下文没有的内容请明确说明「上下文未提及」。\n\n"
        f"问题：{question}\n\n"
        f"上下文：\n{context}"
    )
    result = llm.invoke(prompt)
    return result.content if hasattr(result, "content") else str(result)


def judge_faithfulness(answer: str, context: str, llm: Any) -> FaithfulnessVerdict:
    """LLM-as-judge：判断回答是否忠实于上下文（有无编造）。"""
    prompt = (
        "请判断以下回答是否忠实于给定的上下文：回答中的每一句是否都能在上下文中找到依据，"
        "是否存在上下文未提及的编造内容。\n\n"
        f"上下文：\n{context}\n\n"
        f"回答：\n{answer}\n\n"
        "给出 0-1 的忠实度分数，并说明理由。"
    )
    structured = llm.with_structured_output(FaithfulnessVerdict)
    return structured.invoke(prompt)


def run_faithfulness_eval(
    golden: list[dict],
    *,
    search: Callable[..., list[Any]],
    course_id_for_document: Callable[[str], int | None],
    llm: Any,
    top_k: int = 5,
) -> dict:
    """忠实度评估：检索上下文 → 生成回答 → LLM 判分。

    llm 需为 thinking=False 的模型（结构化判分依赖 tool_choice）。
    返回 {total, avg_faithfulness, items}。
    """
    items: list[dict] = []
    score_sum = 0.0

    for item in golden:
        question = item["question"]
        course_id = course_id_for_document(item["expected_document"])
        docs = search(question, course_id=course_id, top_k=top_k)
        context = "\n".join(d.page_content for d in docs)

        answer = generate_answer_from_context(question, context, llm)
        verdict = judge_faithfulness(answer, context, llm)
        score_sum += verdict.score

        items.append(
            {
                "id": item["id"],
                "question": question,
                "faithfulness": round(verdict.score, 3),
                "rationale": verdict.rationale,
            }
        )

    n = len(items)
    return {
        "total": n,
        "avg_faithfulness": round(score_sum / n, 3) if n else 0.0,
        "items": items,
    }
