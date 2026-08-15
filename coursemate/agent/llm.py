"""LLM 客户端创建。"""

from __future__ import annotations

from langchain_deepseek import ChatDeepSeek

from coursemate.config import get_settings


def get_llm(temperature: float = 0.2, *, thinking: bool = True) -> ChatDeepSeek:
    """创建 DeepSeek 聊天模型客户端。

    temperature 说明：
    - 出题用 0.4 左右，允许一定创造性；
    - 批改用 0.0，追求稳定一致的判断。

    thinking 说明：
    - DeepSeek V4 默认开启思考模式，该模式不接受 tool_choice；
    - 结构化输出依赖 tool_choice 强制模型按 Schema 返回，
      因此这类调用必须传 thinking=False 关闭思考模式，否则 API 返回 400。
    """
    settings = get_settings()
    return ChatDeepSeek(
        model=settings.LLM_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=temperature,
        extra_body={"thinking": {"type": "disabled"}} if not thinking else None,
    )
