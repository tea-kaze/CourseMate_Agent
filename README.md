# 📚 CourseMate：课程学习与刷题助手

一个面向「课程资料学习 + 刷题巩固」的 Web 应用。课程问答使用 LangGraph ReAct Agent 完成检索与回答；自动出题和批改使用固定编排的 RAG + 结构化 LLM 工作流，最后通过错题本复盘薄弱知识点。

## 功能流程

```mermaid
flowchart LR
    A[上传课程资料] --> B[文档解析与向量化]
    B --> C[(Milvus 向量库)]
    B --> D[(PostgreSQL 业务数据)]
    C --> E[Agent 检索问答]
    C --> F[自动出题]
    F --> G[在线作答与批改]
    G --> H[错题本与知识点统计]
    H --> E
```

四大功能：

1. **资料管理**：上传 PDF / Markdown / TXT / Word（.docx），自动解析、切分、向量化入库；入库和删除使用状态机记录中间状态及失败原因，失败删除可以重试。
2. **课程问答**：Agent 检索课程资料后回答，回答带来源引用；支持多会话管理
   （新建/切换/删除，PostgreSQL 持久化，重启后记录不丢）；回答流式输出（SSE 逐 token）；
   长对话自动上下文压缩（增量摘要 + 最近消息窗口），控制 token 成本并保持连贯；
   资料中没有的内容会明确说明，不编造。
3. **刷题练习**：按课程、知识点、题型（单选/多选/简答/混合）自动生成题目，在线作答并批改。
4. **错题本**：历史作答记录、正确率、按题型与知识点的错误分布；近期错题支持按题型、知识点筛选。

## 技术栈与架构

- **语言/工程**：Python 3.12、uv 项目管理
- **问答 Agent**：LangChain 1.x + LangGraph（ReAct Agent，课程范围由服务端固定）
- **刷题工作流**：RAG 检索 + Pydantic 结构化 LLM 输出（固定步骤，不由 Agent 自主选路）
- **模型**：DeepSeek（主模型）、硅基流动 bge-m3（Embedding API）
- **RAG**：LangChain Loader + RecursiveCharacterTextSplitter + Milvus 向量库
- **后端**：FastAPI（REST API，Swagger 文档）
- **前端**：Streamlit（四页面）
- **存储**：Docker/远程 Milvus（向量）+ PostgreSQL（业务数据与自动化测试）
- **可观测性**：LangSmith（可选，设置密钥即自动 trace Agent 每次调用）

架构示意：

```mermaid
flowchart TB
    subgraph Frontend[Streamlit Web]
        P1[资料管理] & P2[课程问答] & P3[刷题练习] & P4[错题本]
    end
    subgraph Backend[FastAPI]
        API[文档/问答/出题/批改/统计接口]
    end
    subgraph Chat[检索问答]
        AGENT[LangGraph ReAct Agent] --> SEARCH[课程范围检索]
    end
    subgraph Quiz[出题与批改]
        GEN[RAG 出题工作流] & GRADE[结构化批改工作流]
    end
    subgraph Storage[存储层]
        MILVUS[(Milvus 向量库)]
        DB[(PostgreSQL)]
    end
    Frontend --> API
    API --> Chat & Quiz
    SEARCH --> MILVUS
    GEN --> MILVUS
    API --> DB
    Quiz --> DB
```

## 快速开始

### 1. 环境准备

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL，并提前创建 CourseMate 使用的数据库和账号
- Docker Desktop（本地运行 Milvus 时需要；也可使用可访问的托管 Milvus）

### 2. 安装依赖

在 PowerShell 中进入项目目录并同步依赖：

```powershell
Set-Location 'D:\Code\Agent_Project\个人项目'
uv sync
```

### 3. 配置环境变量

首次运行且项目中还没有 `.env` 时：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少配置以下字段：

```dotenv
DATABASE_URL=postgresql+psycopg://用户名:密码@数据库地址:5432/coursemate
TEST_DATABASE_URL=postgresql+psycopg://用户名:密码@数据库地址:5432/coursemate_test
DEEPSEEK_API_KEY=你的密钥
SILICONFLOW_API_KEY=你的密钥
MILVUS_URI=http://localhost:19530
MILVUS_TOKEN=
MILVUS_COLLECTION=coursemate_kb
UPLOAD_DIR=data/uploads
MAX_UPLOAD_MB=50
```

`DATABASE_URL` 和 `MILVUS_URI` 是运行时必填配置。数据库只接受 PostgreSQL，Milvus 只接受
带主机名的 `http://` 或 `https://` 地址；缺失或传入本地文件路径时会在启动阶段明确失败，
不会回退到其他存储。密码含 `@`、`:`、`/` 等字符时，需要先做 URL 编码。

`TEST_DATABASE_URL` 只用于 pytest，必须指向独立且名称以 `_test` 结尾的数据库，并且不能与
`DATABASE_URL` 指向同一个数据库。

`MAX_UPLOAD_MB` 默认 50，按 `1024 * 1024` 字节计算。后端最多读取“上限 + 1 字节”用于
判定超限，超过后返回 HTTP 413；聊天当前消息和请求历史中的单条消息最多 4000 字符，
请求历史最多 50 条。

### 4. 准备 Milvus

**本地开发：Docker Milvus（推荐）**

项目的 `docker-compose.yml` 只启动 Milvus、etcd 和 MinIO，不会启动 PostgreSQL：

```powershell
docker compose up -d
docker compose ps
```

等待三个服务进入 `running` 或 `healthy`，并确认 `.env` 中配置：

```dotenv
MILVUS_URI=http://localhost:19530
```

使用托管 Milvus 时改为服务商提供的 HTTPS 地址，并按要求填写 token：

```dotenv
MILVUS_URI=https://你的-Milvus-地址
MILVUS_TOKEN=你的-token
```

### 5. 升级 PostgreSQL

首次启动以及拉取包含数据库结构变更的代码后，都执行：

```powershell
uv run alembic upgrade head
uv run alembic current
```

迁移命令读取 `.env` 中的 `DATABASE_URL`，可初始化空数据库，也可升级已有数据库；重复执行
不会清空现有数据。当前版本应显示 `20260816_0002 (head)`。

### 6. 启动后端与前端

终端 1 启动 FastAPI：

```powershell
Set-Location 'D:\Code\Agent_Project\个人项目'
.\scripts\run_api.ps1
```

终端 2 启动 Streamlit：

```powershell
Set-Location 'D:\Code\Agent_Project\个人项目'
.\scripts\run_web.ps1
```

启动完成后访问：

- Web：<http://localhost:8501>
- API 健康检查：<http://127.0.0.1:8000/health>
- Swagger：<http://127.0.0.1:8000/docs>

如果 PowerShell 执行策略阻止脚本，可直接执行等价命令：

```powershell
uv run uvicorn coursemate.app.main:app --reload --port 8000
uv run streamlit run coursemate/web/app.py
```

正确的启动顺序是：

```text
PostgreSQL + Milvus -> Alembic 迁移 -> FastAPI -> Streamlit
```

### 7. 停止服务

在后端和前端各自的终端按 `Ctrl+C`。需要同时停止 Docker Milvus 时执行：

```powershell
docker compose stop
```

不要使用 `docker compose down -v`，该命令会删除 Milvus 持久化卷。

### 8. 导入演示资料（可选）

```powershell
uv run python scripts/seed_demo.py
```

内置演示资料位于 `data/demo/`，覆盖操作系统、数据库、Java、英语四个课程
（文件名格式「课程名-主题.md」，导入时自动归入对应课程）。当前脚本重复运行会产生重复文档，
建议只在空数据环境执行一次。

### 9. 清理孤儿数据（可选）

先使用只读模式检查候选项：

```powershell
uv run python scripts/cleanup_orphans.py --dry-run
```

如果 Milvus 集合为空但 PostgreSQL 仍存在 `ready` 文档，脚本会拒绝实际删除，避免连接错误或
向量迁移期间误删全部元数据。只有在确认向量确实已经丢失时，才能显式添加
`--allow-empty-milvus` 执行危险清理。

## 项目结构

```text
个人项目/
├── coursemate/
│   ├── config.py          # 全局配置（.env）
│   ├── agent/             # Agent 层：LLM、Schema、工具、LangGraph Agent、上下文压缩
│   ├── app/               # FastAPI 层：路由、文档入库服务、请求模型
│   ├── db/                # SQLAlchemy 模型、会话、仓库函数（含课程问答会话/消息）
│   ├── rag/               # 文档加载/切分、Embedding、Milvus 向量库
│   ├── evaluation.py      # RAG 检索/忠实度评估逻辑
│   └── web/               # Streamlit 前端（4 个页面）
├── docs/                  # 设计文档（含课程问答会话管理设计）
├── migrations/            # Alembic 数据库迁移脚本
├── scripts/
│   ├── seed_demo.py       # 导入演示资料
│   ├── demo_e2e.py        # 端到端功能验证脚本
│   ├── eval_rag.py        # RAG 检索/忠实度评估
│   └── cleanup_orphans.py # 清理孤儿文档与空课程
├── data/
│   ├── demo/              # 演示资料
│   ├── eval/              # RAG 评估 golden set
│   └── uploads/           # 上传的文档原文
├── tests/                 # 单元测试
├── docker-compose.yml     # Milvus + etcd + MinIO（不包含 PostgreSQL）
├── .env.example           # 环境变量模板
└── pyproject.toml
```

## API 一览（Swagger：http://localhost:8000/docs）

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/courses` | 课程列表（只统计 `ready` 文档） |
| POST | `/courses` | 创建课程 |
| GET | `/documents` | 文档列表（只返回 `ready` 文档） |
| POST | `/documents` | 上传文档入库（multipart：file + course_name） |
| DELETE | `/documents/{id}` | 删除文档（含向量与原文；资源失败返回 503，可重试） |
| POST | `/chat` | Agent 对话（会话课程范围固定；长对话自动上下文压缩） |
| POST | `/chat/stream` | Agent 流式对话（固定课程范围，SSE 逐 token 返回） |
| GET | `/chat/sessions` | 会话列表（按最后活动时间倒序） |
| POST | `/chat/sessions` | 新建会话（课程范围创建后不可修改） |
| GET | `/chat/sessions/{id}/messages` | 读取某会话的全部消息 |
| DELETE | `/chat/sessions/{id}` | 删除会话（级联删除消息） |
| POST | `/questions/generate` | 自动出题（响应不含答案与解析；无检索资料时返回 409） |
| POST | `/questions/{id}/grade` | 批改作答（成功后返回答案与解析） |
| GET | `/stats/mistakes` | 错题统计（可按课程、题型、知识点过滤） |
| GET | `/health` | 健康检查 |

## 测试

测试账号需要拥有在 `coursemate_test` 中创建和删除 schema 的权限。普通测试不会连接业务 Milvus
集合，也不会调用 DeepSeek、硅基流动或 LangSmith：

```powershell
uv run pytest -m "not integration" -q
```

所有数据库测试都使用 `TEST_DATABASE_URL` 中随机生成的临时 schema，测试结束后执行
`DROP SCHEMA ... CASCADE`；配置缺失、指向开发库或数据库名不以 `_test` 结尾时，pytest 会拒绝运行。

远程 Milvus 冒烟测试会创建并删除唯一的 `coursemate_test_*` 集合，需要显式执行：

```powershell
uv run pytest tests/test_milvus_integration.py -m integration -q
```

测试覆盖：文档加载与切分（含 .docx 解析）、空 PDF/空 Word 报错、课程/文档/题目/
作答的仓库逻辑、错题统计与题型/知识点筛选、会话与消息持久化、上下文压缩
（增量摘要/失败降级）、入库/删除补偿与迁移、课程隔离、出题与批改的公开接口契约，
聊天事务边界、请求历史校验、SSE 错误响应、空知识库出题保护，以及问答/刷题/错题本页面的
Streamlit AppTest 交互测试。

## RAG 评估

评估脚本独立于主流程，可随时对当前入库的资料跑分：

```bash
# 检索评估（确定性，无需 LLM）：关键词覆盖率 + 文档命中率
uv run python scripts/eval_rag.py

# 附加答案忠实度评估（LLM-as-judge，较慢）
uv run python scripts/eval_rag.py --faithfulness
```

- **golden set**：`data/eval/golden_set.json`，26 条标注问题覆盖四门演示课程；
- **指标**：关键词覆盖率、文档命中率（确定性）、答案忠实度（LLM-as-judge）；
- **前置**：先 `uv run python scripts/seed_demo.py` 入库演示资料。

## 技术选型理由

- **问答与刷题分开编排**：课程问答使用 LangGraph ReAct Agent 决定何时检索；出题和批改由 API 直接执行固定的 RAG + 结构化 LLM 步骤，接口行为更容易约束和测试。
- **服务端课程隔离**：会话创建后以 `ChatSession.course_id` 为唯一课程范围，检索工具不接收模型提供的课程 ID，避免提示词或模型工具参数绕过范围。
- **可补偿的文档状态机**：只有 `ready` 文档对列表和检索可见；入库或删除失败保留失败状态，清理脚本与删除接口可继续补偿。
- **Milvus + PostgreSQL 分离**：Docker/远程 Milvus 负责向量检索，PostgreSQL 负责课程、文档状态、会话、题目和作答记录；运行与测试都不提供 SQLite 或本地文件向量库回退。
- **DeepSeek + 硅基流动**：中文效果好、成本低；Embedding 用 API 避免本地模型安装负担。
- **FastAPI + Streamlit**：后端接口标准、可测试、自带 Swagger；前端四页面按功能组织，演示直观。

## 已知限制与后续方向

- 当前为单用户本地模式，未做登录与多租户。
- 错题本提供统计与列表，未做个性化推荐。
- PDF 仅支持带文本层的文件，扫描件需先 OCR（可接入 MinerU）。
- Word 上传仅支持 .docx，旧版 .doc 请先另存为 .docx 后上传。
- 后续可扩展：会话重命名与消息编辑、学习报告生成、登录与多租户隔离。
