from __future__ import annotations

from coursemate.agent import context


def _messages(n: int) -> list[dict]:
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"消息{i}"}
        for i in range(n)
    ]


class _FakeLLM:
    def __init__(self, output: str, required: str = ""):
        self.output = output
        self.required = required

    def invoke(self, prompt):
        assert self.required in prompt
        return type("R", (), {"content": self.output})()


def test_short_conversation_not_compressed():
    msgs = _messages(5)
    ctx, summary = context.build_chat_context(msgs, summary="", llm=None)
    assert ctx == msgs
    assert summary == ""


def test_long_conversation_keeps_recent_and_summarizes_old():
    msgs = _messages(30)
    ctx, summary = context.build_chat_context(
        msgs, summary="", llm=_FakeLLM("旧对话摘要", required="消息0")
    )
    assert summary == "旧对话摘要"
    assert ctx[0] == {"role": "user", "content": "[对话摘要] 旧对话摘要"}
    assert ctx[1:] == msgs[-10:]


def test_summary_is_incrementally_updated():
    msgs = _messages(30)
    ctx, summary = context.build_chat_context(
        msgs, summary="此前摘要", llm=_FakeLLM("新摘要", required="此前摘要")
    )
    assert summary == "新摘要"
    assert ctx[0]["content"] == "[对话摘要] 新摘要"


def test_summarization_failure_falls_back_to_sliding_window():
    class BoomLLM:
        def invoke(self, prompt):
            raise RuntimeError("boom")

    msgs = _messages(30)
    ctx, summary = context.build_chat_context(msgs, summary="旧值", llm=BoomLLM())
    assert summary == "旧值"
    assert ctx == msgs[-10:]
