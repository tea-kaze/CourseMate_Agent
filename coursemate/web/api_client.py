"""Streamlit 页面访问 FastAPI 的客户端。"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import streamlit as st


def api_base() -> str:
    """后端地址：默认本机 8000 端口，可用环境变量 COURSEMATE_API 覆盖。"""
    return os.environ.get("COURSEMATE_API", "http://127.0.0.1:8000").rstrip("/")


def _client() -> httpx.Client:
    return httpx.Client(base_url=api_base(), timeout=120)


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return response.text.strip()[:500] or "后端未返回错误内容"
    if isinstance(payload, dict):
        detail = payload.get("detail")
    else:
        detail = payload
    return str(detail) if detail else "后端未返回错误内容"


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code >= 400:
        raise RuntimeError(
            f"后端请求失败（HTTP {response.status_code}）：{_response_detail(response)}"
        )


def _response_json(response: httpx.Response) -> Any:
    _raise_for_status(response)
    try:
        return response.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        content_type = response.headers.get("content-type", "未知类型")
        raise RuntimeError(
            f"后端返回无法解析的响应（HTTP {response.status_code}，{content_type}）"
        ) from exc


@st.cache_data(ttl=10)
def get_courses() -> list[dict]:
    """课程列表（10 秒缓存，避免每次重绘都打后端）。"""
    with _client() as client:
        response = client.get("/courses")
    return _response_json(response)


@st.cache_data(ttl=10)
def get_documents() -> list[dict]:
    with _client() as client:
        response = client.get("/documents")
    return _response_json(response)


def upload_document(filename: str, content: bytes, course_name: str) -> dict:
    with _client() as client:
        resp = client.post(
            "/documents",
            files={"file": (filename, content)},
            data={"course_name": course_name},
        )
    return _response_json(resp)


def delete_document(document_id: int) -> None:
    with _client() as client:
        resp = client.delete(f"/documents/{document_id}")
    _raise_for_status(resp)


def chat(
    message: str,
    course_id: int | None = None,
    history: list[dict] | None = None,
    session_id: int | None = None,
) -> dict:
    with _client() as client:
        resp = client.post(
            "/chat",
            json={
                "message": message,
                "course_id": course_id,
                "history": history or [],
                "session_id": session_id,
            },
        )
    return _response_json(resp)


def chat_stream(
    message: str,
    course_id: int | None = None,
    history: list[dict] | None = None,
    session_id: int | None = None,
):
    """流式对话：逐 token 产出回答文本（生成器）。

    后端返回 SSE；此处解析 data 事件，遇 error 抛异常，meta/done 忽略。
    页面在流结束后 rerun，从 API 重读完整消息。
    """
    with httpx.Client(
        base_url=api_base(), timeout=httpx.Timeout(300.0, connect=10.0)
    ) as client:
        with client.stream(
            "POST",
            "/chat/stream",
            json={
                "message": message,
                "course_id": course_id,
                "history": history or [],
                "session_id": session_id,
            },
        ) as resp:
            if resp.status_code >= 400:
                resp.read()
            _raise_for_status(resp)
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if not payload:
                    continue
                event = json.loads(payload)
                etype = event.get("type")
                if etype == "token":
                    yield event.get("content", "")
                elif etype == "error":
                    raise RuntimeError(event.get("message", "流式问答失败"))


def list_chat_sessions() -> list[dict]:
    with _client() as client:
        resp = client.get("/chat/sessions")
    return _response_json(resp)


def create_chat_session(course_id: int | None = None) -> dict:
    with _client() as client:
        resp = client.post("/chat/sessions", json={"course_id": course_id})
    return _response_json(resp)


def delete_chat_session(session_id: int) -> None:
    with _client() as client:
        resp = client.delete(f"/chat/sessions/{session_id}")
    _raise_for_status(resp)


def list_chat_messages(session_id: int) -> list[dict]:
    with _client() as client:
        resp = client.get(f"/chat/sessions/{session_id}/messages")
    return _response_json(resp)


def generate_questions(
    course_id: int, topic: str, count: int, qtype: str
) -> list[dict]:
    with _client() as client:
        resp = client.post(
            "/questions/generate",
            json={
                "course_id": course_id,
                "topic": topic,
                "count": count,
                "qtype": qtype,
            },
        )
    return _response_json(resp)


def grade(question_id: int, user_answer: str) -> dict:
    with _client() as client:
        resp = client.post(
            f"/questions/{question_id}/grade",
            json={"user_answer": user_answer},
        )
    return _response_json(resp)


def mistake_stats(
    course_id: int | None = None,
    qtype: str | None = None,
    topic: str | None = None,
) -> dict:
    params = {}
    if course_id:
        params["course_id"] = course_id
    if qtype:
        params["qtype"] = qtype
    if topic:
        params["topic"] = topic
    with _client() as client:
        resp = client.get("/stats/mistakes", params=params)
    return _response_json(resp)
