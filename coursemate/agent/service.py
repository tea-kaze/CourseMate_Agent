"""Agent 服务：检索、出题、批改、索引四类能力。

工具保持纯函数（不写数据库），持久化由 API 层负责。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.tools import tool
from langchain_core.vectorstores import VectorStoreRetriever
from loguru import logger
from pydantic import BaseModel, ValidationError

from coursemate.agent.llm import get_llm
from coursemate.agent.schemas import GradeResult, QuestionSet
from coursemate.config import get_settings
from coursemate.db.repo import get_course_index
from coursemate.db.session import get_session
from coursemate.rag.vectorstore import get_vectorstore


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
STRUCTURED_OUTPUT_ATTEMPTS = 2
STRUCTURED_OUTPUT_RETRY_INSTRUCTION = (
    "\n\n上一次输出未通过结构校验。请严格按照结构化输出 Schema 返回完整字段，"
    "不要省略任何必填字段。"
)


class NoRelevantCourseMaterialError(Exception):
    def __init__(self) -> None:
        super().__init__("课程资料库为空或未检索到相关内容，请先上传相关资料后再出题。")


def _invoke_structured(
    runnable: Any,
    prompt: str,
    schema: type[StructuredModel],
) -> StructuredModel:
    """Invoke a structured runnable and retry one schema/parser failure."""
    for attempt in range(1, STRUCTURED_OUTPUT_ATTEMPTS + 1):
        try:
            result = runnable.invoke(
                prompt
                if attempt == 1
                else prompt + STRUCTURED_OUTPUT_RETRY_INSTRUCTION
            )
            if isinstance(result, schema):
                return result
            return schema.model_validate(result)
        except (ValidationError, OutputParserException) as exc:
            if attempt == STRUCTURED_OUTPUT_ATTEMPTS:
                raise
            logger.warning(
                "结构化输出校验失败，准备重试 attempt={}/{} error_type={}",
                attempt,
                STRUCTURED_OUTPUT_ATTEMPTS,
                type(exc).__name__,
            )

    raise RuntimeError("unreachable structured output state")


def _format_docs(docs: list[Any]) -> str:
    """把检索到的文档拼成带编号与来源引用的文本。

    这样 Agent 回答时可以引用"第几份资料"，用户也能追溯答案来源。
    """
    blocks: list[str] = []
    for i, doc in enumerate(docs, 1):
        md = doc.metadata or {}
        source = md.get("source") or md.get("filename") or "未知来源"
        page = md.get("page")
        page_txt = f"（第 {page + 1} 页）" if page is not None else ""
        blocks.append(f"[{i}] 来源：{source}{page_txt}\n{doc.page_content}")
    return "\n\n".join(blocks)


class CourseMateService:
    """封装 Agent 所需能力，供工具与 API 复用。

    设计要点：工具保持"纯函数"（不直接写数据库），持久化由 API 层负责，
    这样 Agent 的每个能力都可以单独被 API 直接调用，也方便单测。
    """

    def __init__(self) -> None:
        self._vectorstore = None
        self._retriever: VectorStoreRetriever | None = None

    # ---- 检索 ----
    def _ensure_retriever(self) -> VectorStoreRetriever:
        """懒加载 Milvus 检索器（首次使用时才建立连接）。"""
        if self._retriever is None:
            self._vectorstore = get_vectorstore()
            self._retriever = self._vectorstore.as_retriever(
                search_kwargs={"k": get_settings().TOP_K}
            )
        assert self._retriever is not None
        return self._retriever

    def search(
        self, query: str, course_id: int | None = None, top_k: int | None = None
    ) -> list[Any]:
        """向量检索。

        - course_id 非空时通过 Milvus 元数据过滤，只搜指定课程的片段；
        - top_k 默认取配置中的 TOP_K（5）。
        """
        retriever = self._ensure_retriever()
        invoke_kwargs: dict[str, Any] = {}
        if course_id is not None:
            # Milvus 动态字段为顶层字段，过滤表达式直接引用字段名
            invoke_kwargs["expr"] = f"course_id == {course_id}"
        if top_k is not None:
            invoke_kwargs["k"] = top_k
        return (
            retriever.invoke(query, **invoke_kwargs)
            if invoke_kwargs
            else retriever.invoke(query)
        )

    def search_as_text(
        self, query: str, course_id: int | None = None, top_k: int | None = None
    ) -> str:
        docs = self.search(query, course_id=course_id, top_k=top_k)
        if not docs:
            return "（资料库中没有检索到相关内容）"
        return _format_docs(docs)

    # ---- 出题 ----
    def generate_questions(
        self,
        course_id: int,
        topic: str = "",
        count: int = 5,
        qtype: str = "mixed",
    ) -> QuestionSet:
        """基于课程资料生成练习题。

        流程：先用检索工具召回与主题相关的资料片段作为上下文，
        再让 LLM 以结构化输出（Pydantic Schema）生成题目，保证字段契约稳定。
        """
        course_name = self._course_name(course_id)
        docs = self.search(
            topic or course_name, course_id=course_id, top_k=max(count * 2, 5)
        )
        if not docs:
            raise NoRelevantCourseMaterialError()
        context = _format_docs(docs)
        prompt = (
            f"课程：{course_name}\n"
            f"知识点/主题：{topic or '课程整体'}，要求题型：{qtype}\n"
            f"请基于以下课程资料生成 {count} 道练习题：\n\n{context}\n\n"
            "要求：题目必须严格依据资料内容，简答题给出参考答案与解析。"
        )
        llm = get_llm(temperature=0.4, thinking=False).with_structured_output(QuestionSet)
        return _invoke_structured(llm, prompt, QuestionSet)

    # ---- 批改 ----
    def grade_answer(
        self,
        question: str,
        reference_answer: str,
        user_answer: str,
        context: str = "",
        options: list[str] | None = None,
    ) -> GradeResult:
        """批改一道题。

        客观题由 LLM 严格比对选项；简答题根据要点覆盖情况评分，
        同时输出错误原因与建议复习的知识点。
        """
        options_block = ""
        if options:
            options_block = "选择题选项：\n" + "\n".join(options) + "\n\n"
        prompt = (
            "请批改以下作答。\n\n"
            f"题目：{question}\n"
            f"{options_block}"
            f"参考答案：{reference_answer}\n"
            f"学生作答：{user_answer}\n"
            f"课程资料参考（可为空）：\n{context[:4000] if context else '（无）'}\n\n"
            "要求：选择题严格按选项比对；学生作答中的字母（A/B/C…）对应上述选项，"
            "请据此逐项判断学生是否选择了该选项；简答题根据要点是否覆盖评分，给出具体错误原因。"
        )
        llm = get_llm(temperature=0.0, thinking=False).with_structured_output(GradeResult)
        return _invoke_structured(llm, prompt, GradeResult)

    # ---- 索引 ----
    def course_index(self) -> list[dict]:
        with get_session() as session:
            return get_course_index(session)

    def _course_name(self, course_id: int) -> str:
        with get_session() as session:
            from coursemate.db.repo import get_course

            course = get_course(session, course_id)
            return course.name if course else f"课程#{course_id}"


@lru_cache
def get_service() -> CourseMateService:
    return CourseMateService()


def build_tools(
    service: CourseMateService | None = None,
    *,
    course_id: int | None = None,
) -> list[Any]:
    """构建聊天 Agent 的只读检索工具。

    每个工具用 @tool 装饰器定义，带清晰的 description，
    模型才能正确决定何时调用哪个工具（这是 ReAct Agent 的关键）。
    """
    svc = service or get_service()

    @tool
    def search_knowledge(query: str) -> str:
        """在课程知识库中检索与 query 相关的资料片段，返回带来源引用的文本。"""
        return svc.search_as_text(query, course_id=course_id)

    @tool
    def get_course_index() -> str:
        """列出已入库的课程、文档数量与文档名，供确认检索范围。"""
        return str(svc.course_index())

    tools = [search_knowledge]
    if course_id is None:
        tools.append(get_course_index)
    return tools
