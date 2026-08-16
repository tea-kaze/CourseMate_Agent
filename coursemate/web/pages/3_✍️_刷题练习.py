from __future__ import annotations

import streamlit as st

from coursemate.web.api_client import generate_questions, get_courses, grade
from coursemate.web.quiz_state import (
    clear_old_results,
    correct_options,
    get_grade_result,
    is_graded,
    mark_graded,
    selected_options,
)


st.set_page_config(page_title="刷题练习", page_icon="✍️")
st.title("✍️ 刷题练习")

courses = get_courses()
if not courses:
    st.info("还没有课程资料，请先到「资料管理」上传。")
    st.stop()

with st.form("gen_form"):
    course_opts = {f"{c['name']}（#{c['id']}）": c["id"] for c in courses}
    course_name = st.selectbox("课程", list(course_opts))
    topic = st.text_input("知识点（可选）", placeholder="例如：进程调度")
    col1, col2 = st.columns(2)
    count = col1.number_input("题目数量", min_value=1, max_value=10, value=3)
    qtype = col2.selectbox("题型", ["mixed", "single", "multiple", "short"])
    generated = st.form_submit_button("生成题目", use_container_width=True)

if generated:
    with st.spinner("Agent 检索资料并生成题目中..."):
        try:
            # 生成结果存 session_state，页面重绘后题目仍然保留
            st.session_state.quiz_questions = generate_questions(
                course_opts[course_name], topic, int(count), qtype
            )
            st.session_state.quiz_course = course_opts[course_name]
            st.session_state.quiz_course_name = course_name
            # 新题组：清理旧题目的批改状态，避免串扰
            clear_old_results(
                [q["id"] for q in st.session_state.quiz_questions],
                st.session_state,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"出题失败：{exc}")
            st.session_state.pop("quiz_questions", None)

questions = st.session_state.get("quiz_questions")
if questions:
    st.success(f"已生成 {len(questions)} 道题（课程：{st.session_state.quiz_course_name}）")
    for i, q in enumerate(questions, 1):
        with st.container(border=True):
            type_label = {
                "single": "单选题",
                "multiple": "多选题",
                "short": "简答题",
                "mixed": "综合",
            }.get(q["qtype"], q["qtype"])
            st.markdown(f"**{i}. [{type_label}] {q['stem']}**")
            if q["topic"]:
                st.caption(f"知识点：{q['topic']}")
            key = f"ans_{q['id']}"
            # 已批改：只显示结果，不再渲染作答控件与提交按钮（每题只能答一次）
            if is_graded(q["id"], st.session_state):
                result = get_grade_result(q["id"], st.session_state)
                icon = "✅" if result["is_correct"] else "❌"
                # 保留原题与各选项，标识用户所选答案与正确答案
                if q["options"]:
                    user_opts = selected_options(
                        result.get("user_answer", ""), q["options"]
                    )
                    correct_opts = correct_options(
                        result.get("correct_answer", ""),
                        q["options"],
                    )
                    for opt in q["options"]:
                        marks = []
                        if opt in user_opts:
                            marks.append("我的答案")
                        if opt in correct_opts:
                            marks.append("正确答案")
                        suffix = f"（{'、'.join(marks)}）" if marks else ""
                        st.markdown(f"- {opt}{suffix}")
                else:
                    st.markdown(f"**你的回答**：{result.get('user_answer', '')}")
                st.markdown(f"{icon} 得分 **{result['score']}** / 100")
                # 直观展示用户答案与正确答案
                if q["options"]:
                    user_opts = selected_options(
                        result.get("user_answer", ""), q["options"]
                    )
                    correct_opts = correct_options(
                        result.get("correct_answer", ""),
                        q["options"],
                    )
                    st.markdown(f"**你的答案**：{result.get('user_answer') or '（未作答）'}")
                    st.markdown(
                        f"**正确答案**：{result.get('correct_answer', '')}"
                    )
                else:
                    st.markdown(f"**你的答案**：{result.get('user_answer', '')}")
                    st.markdown(f"**正确答案**：{result.get('correct_answer', '')}")
                st.markdown(f"**反馈**：{result['feedback']}")
                if result.get("explanation"):
                    st.markdown(f"**题目解析**：{result['explanation']}")
                if result.get("knowledge_point"):
                    st.markdown(f"**建议复习**：{result['knowledge_point']}")
                st.caption("本题已完成作答")
                continue

            # 未批改：渲染作答控件
            if q["options"]:
                if q["qtype"] == "multiple":
                    # 多选题：用勾选式 checkbox 逐项展示，允许多选；提交选项字母（A/B/C…），
                    # 避免选项文本自身含「、」时被切分导致识别失败
                    selected = []
                    for i, opt in enumerate(q["options"]):
                        if st.checkbox(opt, key=f"{key}_{opt}"):
                            selected.append(chr(ord("A") + i))
                    user_answer = "、".join(selected) if selected else ""
                else:
                    options = q["options"]
                    sel = st.radio(
                        "选择答案", options, key=key, label_visibility="collapsed"
                    )
                    user_answer = sel
            else:
                user_answer = st.text_area("你的回答", key=key, height=90)

            if st.button("提交批改", key=f"grade_{q['id']}"):
                if not user_answer.strip():
                    st.warning("请先作答再提交")
                    continue
                with st.spinner("正在批改..."):
                    try:
                        r = grade(q["id"], user_answer)
                        # 保存批改结果：页面重绘后反馈仍显示
                        mark_graded(
                            q["id"],
                            {**r, "user_answer": user_answer},
                            st.session_state,
                        )
                        # 立即重绘，隐藏作答控件与提交按钮，防止重复作答
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"批改失败：{exc}")
