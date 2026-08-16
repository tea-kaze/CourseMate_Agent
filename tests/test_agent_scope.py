from __future__ import annotations

from coursemate.agent.service import build_tools


class FakeService:
    def __init__(self):
        self.search_calls: list[tuple[str, int | None]] = []

    def search_as_text(self, query: str, course_id: int | None = None):
        self.search_calls.append((query, course_id))
        return "result"

    def course_index(self):
        return []


def test_scoped_search_tool_forces_server_course_id():
    service = FakeService()
    tools = build_tools(service, course_id=7)
    search = next(item for item in tools if item.name == "search_knowledge")

    assert "course_id" not in search.args_schema.model_fields
    assert search.invoke({"query": "进程调度"}) == "result"
    assert service.search_calls == [("进程调度", 7)]


def test_scoped_agent_does_not_expose_course_index_tool():
    scoped_names = {tool.name for tool in build_tools(FakeService(), course_id=7)}
    global_names = {tool.name for tool in build_tools(FakeService(), course_id=None)}

    assert "get_course_index" not in scoped_names
    assert "get_course_index" in global_names
