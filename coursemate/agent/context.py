"""课程问答上下文压缩：增量摘要 + 最近消息窗口。

长会话下把超窗的旧消息交给 LLM 压缩成摘要，与最近消息一起发送给模型；
摘要持久化在会话表中，再次超窗时用「旧摘要 + 新增旧消息」做增量更新。
压缩失败时降级为滑动窗口，不阻塞问答。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from coursemate.config import get_settings


SUMMARY_PROMPT = (
    "请将以下对话压缩为简洁的对话摘要（中文）。\n"
    "必须保留：关键问题与结论、用户明确表达过的偏好或要求、尚未完成或待继续的事项。\n"
    "省略：寒暄、重复内容、与主题无关的细节。\n"
    "只输出摘要本身，不要解释。\n\n"
    "{text}"
)


def estimate_chars(messages: list[dict]) -> int:
    """按内容字符数估算上下文长度，避免引入额外 tokenizer。"""
    return sum(len(m.get("content", "")) for m in messages)


def needs_compression(messages: list[dict]) -> bool:
    """消息数超过阈值或估算长度超过预算时触发压缩。"""
    settings = get_settings()
    return len(messages) > settings.CHAT_SUMMARY_THRESHOLD_MESSAGES or estimate_chars(
        messages
    ) > settings.CHAT_HISTORY_CHAR_BUDGET


def _format_messages(messages: list[dict]) -> str:
    return "\n".join(f"{m['role']}: {m['content']}" for m in messages)


def summarize_messages(llm: Any, summary: str, old_messages: list[dict]) -> str:
    """把旧消息（连同已有摘要）压缩成新的对话摘要。"""
    text = _format_messages(old_messages)
    if summary:
        text = f"旧摘要：\n{summary}\n\n新增对话：\n{text}"
    result = llm.invoke(SUMMARY_PROMPT.format(text=text))
    content = result.content if hasattr(result, "content") else str(result)
    return content.strip()


def build_chat_context(
    messages: list[dict], summary: str, llm: Any | None = None
) -> tuple[list[dict], str]:
    """返回 (发送给 Agent 的消息列表, 需要写回的新摘要)。

    未超阈值：原样返回全部消息与旧摘要。
    超阈值：旧消息压缩进摘要，只保留最近 N 条。
    摘要失败：降级为滑动窗口，保留旧摘要。
    """
    if not needs_compression(messages):
        return list(messages), summary
    keep = get_settings().CHAT_KEEP_RECENT_MESSAGES
    recent = messages[-keep:]
    old = messages[:-keep]
    if not old:
        return list(messages), summary
    if llm is None:
        from coursemate.agent.llm import get_llm

        llm = get_llm()
    try:
        new_summary = summarize_messages(llm, summary, old)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"对话摘要生成失败，降级为滑动窗口：{exc}")
        return recent, summary
    ctx: list[dict] = []
    if new_summary:
        ctx.append({"role": "user", "content": f"[对话摘要] {new_summary}"})
    ctx.extend(recent)
    return ctx, new_summary
