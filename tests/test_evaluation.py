"""RAG 检索评估的纯函数测试（不依赖外部 API）。"""

from __future__ import annotations

from coursemate import evaluation


class _Doc:
    def __init__(self, text: str = "", filename: str | None = None):
        self.page_content = text
        self.metadata = {"filename": filename} if filename else {}


def test_keyword_coverage_fraction():
    assert evaluation.keyword_coverage("互斥、循环等待", ["互斥", "循环等待"]) == 1.0
    assert evaluation.keyword_coverage("只有互斥", ["互斥", "不可剥夺"]) == 0.5
    assert evaluation.keyword_coverage("", ["互斥"]) == 0.0


def test_keyword_coverage_empty_keywords_is_full():
    assert evaluation.keyword_coverage("任意文本", []) == 1.0


def test_documents_hit_document_by_filename():
    docs = [
        _Doc(filename="操作系统-进程与调度.md"),
        _Doc(filename="数据库-基础与SQL.md"),
    ]
    assert evaluation.documents_hit_document(docs, "操作系统-进程与调度.md") is True
    assert evaluation.documents_hit_document(docs, "不存在的文档.md") is False


def test_run_eval_with_fake_search():
    golden = [
        {
            "id": "t1",
            "course": "操作系统",
            "question": "死锁条件？",
            "expected_document": "os.md",
            "expected_keywords": ["互斥", "循环等待"],
        }
    ]

    def fake_search(query, course_id=None, top_k=5):
        return [_Doc("互斥、循环等待", "os.md")]

    report = evaluation.run_eval(
        golden, search=fake_search, course_id_for_document=lambda doc: 1, top_k=5
    )
    assert report["avg_keyword_coverage"] == 1.0
    assert report["document_hit_rate"] == 1.0
    assert report["items"][0]["document_hit"] is True
    assert report["items"][0]["keyword_coverage"] == 1.0


def test_generate_answer_from_context():
    class FakeLLM:
        def invoke(self, prompt):
            assert "问题：死锁" in prompt
            assert "上下文" in prompt
            return type("R", (), {"content": "基于上下文的回答"})()

    ans = evaluation.generate_answer_from_context("死锁", "上下文内容", FakeLLM())
    assert ans == "基于上下文的回答"


def test_judge_faithfulness_uses_structured_output():
    from coursemate.evaluation import FaithfulnessVerdict

    class FakeLLM:
        def with_structured_output(self, schema):
            assert schema is FaithfulnessVerdict
            return self

        def invoke(self, prompt):
            assert "忠实" in prompt
            return FaithfulnessVerdict(score=0.9, rationale="全部有依据")

    verdict = evaluation.judge_faithfulness("答", "上下文", FakeLLM())
    assert verdict.score == 0.9
    assert verdict.rationale == "全部有依据"
