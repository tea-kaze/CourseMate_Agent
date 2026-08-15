"""LangGraph ReAct Agent 构建。"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from coursemate.agent.llm import get_llm
from coursemate.agent.service import build_tools


SYSTEM_PROMPT = (
    "你是 CourseMate，一名课程学习与刷题助手。你可以：\n"
    "1. 使用 search_knowledge 检索课程资料并回答知识问题，回答需引用资料来源；\n"
    "2. 使用 generate_questions 根据课程资料生成练习题；\n"
    "3. 使用 grade_answer 批改学生作答；\n"
    "4. 使用 get_course_index 查看已入库的课程与资料。\n"
    "回答要基于资料内容；资料中没有的内容，明确说明“资料中未找到”，不要编造。"
)


def build_agent():
    """构建 LangGraph ReAct Agent。

    create_react_agent 会生成一个"思考-调用工具-观察结果"循环：
    模型根据用户问题决定调用哪个工具，工具返回结果后模型继续推理直到可以回答。
    prompt 中的系统提示词约束了回答行为（必须引用来源、不许编造）。
    """
    llm = get_llm(temperature=0.2)
    return create_react_agent(
        model=llm,
        tools=build_tools(),
        prompt=SYSTEM_PROMPT,
    )
