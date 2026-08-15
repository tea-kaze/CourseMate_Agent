"""Streamlit 页面访问 FastAPI 的客户端。"""

from __future__ import annotations

import os

import httpx
import streamlit as st


def api_base() -> str:
    """后端地址：默认本机 8000 端口，可用环境变量 COURSEMATE_API 覆盖。"""
    return os.environ.get("COURSEMATE_API", "http://127.0.0.1:8000").rstrip("/")


def _client() -> httpx.Client:
    return httpx.Client(base_url=api_base(), timeout=120)


@st.cache_data(ttl=10)
def get_courses() -> list[dict]:
    """课程列表（10 秒缓存，避免每次重绘都打后端）。"""
    with _client() as client:
        return client.get("/courses").json()


@st.cache_data(ttl=10)
def get_documents() -> list[dict]:
    with _client() as client:
        return client.get("/documents").json()


def upload_document(filename: str, content: bytes, course_name: str) -> dict:
    with _client() as client:
        resp = client.post(
            "/documents",
            files={"file": (filename, content)},
            data={"course_name": course_name},
        )
    if resp.status_code >= 400:
        raise RuntimeError(resp.json().get("detail", resp.text))
    return resp.json()


def delete_document(document_id: int) -> None:
    with _client() as client:
        resp = client.delete(f"/documents/{document_id}")
    if resp.status_code >= 400:
        raise RuntimeError(resp.json().get("detail", resp.text))


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
    if resp.status_code >= 400:
        raise RuntimeError(resp.json().get("detail", resp.text))
    return resp.json()


def list_chat_sessions() -> list[dict]:
    with _client() as client:
        resp = client.get("/chat/sessions")
    if resp.status_code >= 400:
        raise RuntimeError(resp.json().get("detail", resp.text))
    return resp.json()


def create_chat_session(course_id: int | None = None) -> dict:
    with _client() as client:
        resp = client.post("/chat/sessions", json={"course_id": course_id})
    if resp.status_code >= 400:
        raise RuntimeError(resp.json().get("detail", resp.text))
    return resp.json()


def delete_chat_session(session_id: int) -> None:
    with _client() as client:
        resp = client.delete(f"/chat/sessions/{session_id}")
    if resp.status_code >= 400:
        raise RuntimeError(resp.json().get("detail", resp.text))


def list_chat_messages(session_id: int) -> list[dict]:
    with _client() as client:
        resp = client.get(f"/chat/sessions/{session_id}/messages")
    if resp.status_code >= 400:
        raise RuntimeError(resp.json().get("detail", resp.text))
    return resp.json()


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
    if resp.status_code >= 400:
        raise RuntimeError(resp.json().get("detail", resp.text))
    return resp.json()


def grade(question_id: int, user_answer: str) -> dict:
    with _client() as client:
        resp = client.post(
            f"/questions/{question_id}/grade",
            json={"question_id": question_id, "user_answer": user_answer},
        )
    if resp.status_code >= 400:
        raise RuntimeError(resp.json().get("detail", resp.text))
    return resp.json()


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
    if resp.status_code >= 400:
        raise RuntimeError(resp.json().get("detail", resp.text))
    return resp.json()
