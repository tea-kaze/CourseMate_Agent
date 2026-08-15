"""Streamlit 入口：导航到四个功能页面。"""

from __future__ import annotations

import streamlit as st

from coursemate.web.api_client import get_courses, get_documents


st.set_page_config(page_title="CourseMate 课程学习与刷题助手", page_icon="📚")

st.title("📚 CourseMate：课程学习与刷题助手")
st.caption("上传课程资料 → 知识问答 → 自动出题 → 答题批改 → 错题分析")

courses = get_courses()
docs = get_documents()
col1, col2 = st.columns(2)
col1.metric("已入库课程", len(courses))
col2.metric("已入库文档", len(docs))

st.divider()
st.markdown(
    """
使用左侧导航进入功能页面：
- **资料管理**：上传 PDF / Markdown / TXT / Word 课程资料，查看与删除
- **课程问答**：针对课程资料提问，回答带来源引用
- **刷题练习**：按课程与题型自动出题，在线作答并批改
- **错题本**：查看历史作答与错题知识点统计
"""
)
