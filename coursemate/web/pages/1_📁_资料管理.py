from __future__ import annotations

import streamlit as st

from coursemate.web.api_client import delete_document, get_courses, get_documents, upload_document


st.set_page_config(page_title="资料管理", page_icon="📁")
st.title("📁 资料管理")

with st.form("upload_form", clear_on_submit=True):
    course_name = st.text_input("课程名称", placeholder="例如：操作系统")
    files = st.file_uploader(
        "上传课程资料（PDF / Markdown / TXT / Word）",
        type=["pdf", "md", "markdown", "txt", "docx"],
        accept_multiple_files=True,
    )
    submitted = st.form_submit_button("开始入库", use_container_width=True)

if submitted:
    # 逐个文件入库：任一文件失败不影响其他文件
    if not course_name.strip():
        st.error("请填写课程名称")
    elif not files:
        st.error("请选择文件")
    else:
        for f in files:
            with st.spinner(f"正在入库：{f.name}（加载 → 切分 → 向量化）..."):
                try:
                    result = upload_document(f.name, f.getvalue(), course_name.strip())
                    st.success(
                        f"✅ {result['filename']}：{result['chunk_count']} 个片段已入库（课程：{result['course_name']}）"
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"❌ {f.name} 入库失败：{exc}")
        st.cache_data.clear()

st.divider()
st.subheader("已入库文档")
courses = get_courses()
docs = get_documents()
if not docs:
    st.info("还没有文档，先上传一份课程资料吧。")
else:
    for doc in docs:
        # 每个文档一行：文件名 + 课程/片段数 + 删除按钮
        col1, col2, col3 = st.columns([2, 1, 1])
        col1.write(f"**{doc['filename']}**")
        col2.write(f"课程：{doc['course_name']} · {doc['chunk_count']} 片段")
        if col3.button("删除", key=f"del_{doc['id']}"):
            try:
                delete_document(doc["id"])
                st.success(f"已删除 {doc['filename']}")
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"删除失败：{exc}")
