# CourseMate 3 分钟演示脚本

## 准备

1. 确认 `.env` 已配置 DeepSeek 与硅基流动密钥。
2. 确认 PostgreSQL 与 Docker/远程 Milvus 可访问，并执行 `uv run alembic upgrade head`。
3. 启动后端：`uv run uvicorn coursemate.app.main:app --port 8000`
4. 启动前端：`uv run streamlit run coursemate/web/app.py`
5. 如使用演示资料，先执行：`uv run python scripts/seed_demo.py`

## 演示流程

### 第 1 分钟：资料入库

- 打开 http://localhost:8501，进入「资料管理」。
- 上传课程讲义 PDF（或演示资料），展示入库日志中的 chunk 数量。
- 说明：文档会被切分成 500~800 字符片段，向量化后存入 Milvus。

### 第 2 分钟：知识问答

- 进入「课程问答」，提问例如：“什么是时间片轮转调度？”
- 展示回答与来源引用；再问一个资料外的问题，展示“资料中未找到”的拒绝行为。
- 说明：主 Agent 通过 search_knowledge 工具检索 top-k 相关片段后组织回答。

### 第 3 分钟：刷题与错题本

- 进入「刷题练习」，选择课程、题型“混合”、数量 3，生成题目。
- 故意答错一题提交，展示批改分数、反馈与参考答案。
- 进入「错题本」，展示作答统计、正确率、按知识点分布。
- 收尾一句：整个闭环 = 资料 → 检索 → 出题 → 批改 → 复盘。

## 面试话术要点

- 为什么问答 Agent 只暴露检索工具：权限边界明确，课程范围由服务端固定，避免模型绕过隔离。
- 为什么 Milvus：支持高维向量索引与元数据过滤，适合课程维度检索。
- 为什么结构化输出：出题和批改用 Pydantic Schema 约束，保证 API 契约稳定。
- 做得好的点：答案带引用、资料外问题明确拒答、删除文档同步清理向量。
