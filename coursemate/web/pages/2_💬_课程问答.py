from __future__ import annotations

import streamlit as st

from coursemate.web.api_client import (
    chat_stream,
    create_chat_session,
    delete_chat_session,
    get_courses,
    list_chat_messages,
    list_chat_sessions,
)


st.set_page_config(page_title="课程问答", page_icon="💬")
st.title("💬 课程问答")

courses = get_courses()
if not courses:
    st.info("还没有课程资料，请先到「资料管理」上传。")
    st.stop()

course_opts = {f"{c['name']}（#{c['id']}）": c["id"] for c in courses}
selected = st.sidebar.selectbox("新会话课程范围", ["全部课程", *course_opts])
new_session_course_id = course_opts.get(selected)

sessions = list_chat_sessions()

if st.session_state.get("qa_session_id") is None and sessions:
    # 首次进入默认打开最近的会话
    st.session_state.qa_session_id = sessions[0]["id"]

with st.sidebar:
    st.subheader("会话")
    if st.button("＋ 新建会话", key="new_session", use_container_width=True):
        created = create_chat_session(course_id=new_session_course_id)
        st.session_state.qa_session_id = created["id"]
        st.rerun()
    for s in sessions:
        title = s["title"] or "新会话"
        current = st.session_state.get("qa_session_id") == s["id"]
        prefix = "● " if current else ""
        if st.button(
            f"{prefix}{title}", key=f"session_{s['id']}", use_container_width=True
        ):
            st.session_state.qa_session_id = s["id"]
            st.rerun()
    if st.session_state.get("qa_session_id") and st.button(
        "🗑 删除当前会话", key="delete_current", use_container_width=True
    ):
        delete_chat_session(st.session_state.qa_session_id)
        st.session_state.pop("qa_session_id", None)
        st.rerun()

session_id = st.session_state.get("qa_session_id")
if session_id is None:
    st.info("点击左侧「＋ 新建会话」开始提问。")
    st.stop()

active_session = next((s for s in sessions if s["id"] == session_id), None)
active_course_id = active_session["course_id"] if active_session else None

messages = list_chat_messages(session_id)
for m in messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("输入你的课程问题，例如：什么是进程调度？")
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            st.write_stream(
                chat_stream(
                    prompt,
                    course_id=active_course_id,
                    session_id=session_id,
                )
            )
            # 重新从 API 读取完整消息，保证与会话一致
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"问答失败：{exc}")
