"""LangGraph ReAct Agent 构建。"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from coursemate.agent.llm import get_llm
from coursemate.agent.service import build_tools


SYSTEM_PROMPT = (
    "你是 CourseMate，一名课程学习助手。你可以使用 search_knowledge "
    "检索课程资料并回答知识问题，回答需引用资料来源；在全库会话中，"
    "还可以使用 get_course_index 查看已入库的课程与资料。\n"
    "回答要基于资料内容；资料中没有的内容，明确说明“资料中未找到”，不要编造。"
)


def build_agent(course_id: int | None = None):
    """构建 LangGraph ReAct Agent。

    create_react_agent 会生成一个"思考-调用工具-观察结果"循环：
    模型根据用户问题决定调用哪个工具，工具返回结果后模型继续推理直到可以回答。
    prompt 中的系统提示词约束了回答行为（必须引用来源、不许编造）。
    """
    llm = get_llm(temperature=0.2)
    prompt = SYSTEM_PROMPT
    if course_id is not None:
        prompt += (
            f"\n当前会话固定在课程 ID {course_id}；检索工具已由服务端绑定该范围，"
            "不得尝试访问其他课程。"
        )
    return create_react_agent(
        model=llm,
        tools=build_tools(course_id=course_id),
        prompt=prompt,
    )
