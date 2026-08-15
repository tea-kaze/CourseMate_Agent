from __future__ import annotations

import streamlit as st

from coursemate.web.api_client import get_courses, mistake_stats
from coursemate.web.quiz_state import correct_options, selected_options


st.set_page_config(page_title="错题本", page_icon="📒")
st.title("📒 错题本")

courses = get_courses()
course_id = None
if courses:
    course_opts = {"全部课程": None, **{f"{c['name']}（#{c['id']}）": c["id"] for c in courses}}
    course_id = st.selectbox("按课程筛选", list(course_opts), format_func=lambda x: x)
    course_id = course_opts[course_id]

QTYPE_LABELS = {"single": "单选题", "multiple": "多选题", "short": "简答题"}

base_stats = mistake_stats(course_id)
if base_stats["total_attempts"] == 0:
    st.info("还没有作答记录，去「刷题练习」做几道题吧。")
    st.stop()

# 顶部三个核心指标：累计作答、答对次数、正确率
c1, c2, c3 = st.columns(3)
c1.metric("累计作答", base_stats["total_attempts"])
c2.metric("答对", base_stats["correct_count"])
c3.metric("正确率", f"{base_stats['accuracy'] * 100:.1f}%")

st.divider()
left, right = st.columns(2)
with left:
    st.subheader("按题型")
    for key, val in base_stats["by_type"].items():
        acc = val["correct"] / val["total"] if val["total"] else 0
        st.progress(acc, text=f"{key}：{val['correct']}/{val['total']}")
with right:
    st.subheader("按知识点")
    for key, val in base_stats["by_topic"].items():
        acc = val["correct"] / val["total"] if val["total"] else 0
        st.progress(acc, text=f"{key}：{val['correct']}/{val['total']}")

st.divider()
st.subheader("近期错题")

# 题型/知识点下拉组合筛选：只过滤近期错题列表，顶部汇总保持全量
type_opts = {"全部题型": None}
for t in base_stats["by_type"]:
    type_opts[QTYPE_LABELS.get(t, t)] = t
topic_opts = {"全部知识点": None}
for t in sorted(base_stats["by_topic"]):
    topic_opts[t] = t

f1, f2 = st.columns(2)
sel_type = f1.selectbox("题型", list(type_opts), key="mistake_type_filter")
sel_topic = f2.selectbox("知识点", list(topic_opts), key="mistake_topic_filter")
qtype_val = type_opts[sel_type]
topic_val = topic_opts[sel_topic]

if qtype_val is None and topic_val is None:
    wrong_attempts = base_stats["wrong_attempts"]
else:
    wrong_attempts = mistake_stats(
        course_id, qtype=qtype_val, topic=topic_val
    )["wrong_attempts"]

if not wrong_attempts:
    st.info("该筛选条件下暂无错题。")
    st.stop()

for item in wrong_attempts:
    with st.expander(
        f"[{QTYPE_LABELS.get(item['qtype'], item['qtype'])}] "
        f"{item['stem'][:50]}{'…' if len(item['stem']) > 50 else ''}"
    ):
        st.markdown(f"**题干**：{item['stem']}")
        options = item.get("options") or []
        if options:
            user_opts = selected_options(item["user_answer"], options)
            correct_opts = correct_options(item["correct_answer"], options)
            for opt in options:
                marks = []
                if opt in user_opts:
                    marks.append("我的答案")
                if opt in correct_opts:
                    marks.append("正确答案")
                suffix = f"（{'、'.join(marks)}）" if marks else ""
                st.markdown(f"- {opt}{suffix}")
        st.markdown(f"**你的答案**：{item['user_answer']}")
        st.markdown(f"**正确答案**：{item['correct_answer']}")
        st.markdown(f"**反馈**：{item['feedback']}")
        st.caption(f"得分 {item['score']} · {item['created_at']}")
