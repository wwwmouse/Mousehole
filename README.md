# mousehole

> 面向个人用户的 **Local-first AI Workspace**：把资料、任务、执行过程和成果沉淀在同一个持续存在的工作空间里。

**当前状态：Phase 1 开发中。** 设计文档已完成；后端工程、PostgreSQL 迁移、Workspace / Project / Task / File 与 Task 文件上下文 API、文档解析已可运行并附带自动化测试；前端工作台页面已实现并通过生产构建。Phase 1 验收（端到端人工检查）仍在收尾。

---

## 这是什么

mousehole 不是 AI 聊天客户端，也不是 Agent 搭建平台。它要验证的是一件事：

> 用户能否在一个持续存在的工作环境中，组织多个项目和任务，引用多份资料，借助 AI 完成实际工作，并把成果保存下来供未来继续使用？

核心闭环：

```text
创建 Project → 上传多份资料 → 创建 Task → 组织上下文
      → 模型分析 → 生成 Markdown Artifact → 重启后继续复用
```

MVP 锁定首个业务场景：**多文档技术资料分析**。

## 核心概念

| 概念 | 一句话职责 |
|---|---|
| Workspace | 长期工作环境（Global Workspace 承载临时任务与跨项目工作） |
| Project | 长期项目组织单元，可归档 |
| Task | 一项具体工作目标，可多次执行；不等于对话 |
| Execution | Task 的一次实际运行，记录状态、模型、结果与文件快照 |
| Conversation | Task 内的交流记录，不承担执行日志与成果存储 |
| File | 统一进入 Global Library 的原始资料，通过引用被 Project / Task 使用 |
| Artifact | 执行产生的独立成果，按 ArtifactSeries 版本化，不覆盖历史 |

## MVP 范围

**必做**：Workspace / Project / Task 管理、文件上传与 PDF·Markdown·TXT 解析、文件继承与排除、OpenAI / DeepSeek / Ollama 接入、Task 内对话与流式输出、确定性 Execution Pipeline、Markdown Artifact 与版本、Execution 状态与实时阶段进度、重启后数据持久化。

**明确不做**：多用户与协作、SaaS 部署、微服务 / K8s、复杂任务队列、RAG 与向量检索、多 Agent 协作、任意 Shell 执行、Skill / Workflow / MCP 管理、WebSocket、Word / Excel / PPT 解析、扫描件 OCR。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Vue Router |
| 后端 | Python 3.14 + FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic + Pytest（PostgreSQL 驱动：纯 Python 的 pg8000） |
| 数据库 | PostgreSQL 16（Docker Compose，本机映射 5433；MVP 不启用 pgvector） |
| 文件 | 本地文件系统 + 数据库元数据，通过 storage_key 定位 |
| 模型 | 统一 Model Service + Provider Adapter（OpenAI / DeepSeek / Ollama） |
| 通信 | REST API + Server-Sent Events（SSE） |
| 执行 | 进程内 Scheduler，默认最多 2 个并发 Execution，DB 状态为唯一事实源 |
| 部署 | Docker Compose（前后端 + PostgreSQL + 持久化目录） |

## 仓库结构

```text
mousehole/
├── AGENTS.md              # AI Coding Agent 的项目级约束（开工前必读）
├── README.md
├── .env.example
├── docker-compose.yml     # PostgreSQL 16（本机映射 5433）
├── docs/                  # 设计文档
├── backend/               # FastAPI + SQLAlchemy + Alembic
│   ├── app/
│   │   ├── api/v1/        # health / workspaces / projects / tasks / files / task_files
│   │   ├── modules/       # workspace / project / task / file / document / context
│   │   ├── infrastructure/# database
│   │   └── shared/        # config / enums / exceptions / db types
│   ├── alembic/versions/  # 数据库迁移
│   ├── tests/             # pytest（SQLite 隔离，不依赖 PostgreSQL）
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/              # Vue 3 + TypeScript + Vite + Pinia
│   └── src/{api,components,router,stores,styles,utils,views}/
├── data/                  # 应用本地配置（不入库，含模型密钥配置）
└── storage/               # 用户文件与 Artifact 物理存储（不入库）
```

## 文档导航

| 文档 | 内容 |
|---|---|
| [PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) · [中文版](docs/PRODUCT_SPEC_中文版.md) | 产品愿景、设计原则、能力库、长期方向 |
| [MVP_SPEC.md](docs/MVP_SPEC.md) | MVP 范围、P0/P1、验收标准、非目标 |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | 实体、字段、关系、删除规则、实现优先级 |
| [TECHNICAL_DECISIONS.md](docs/TECHNICAL_DECISIONS.md) | 技术选型与工程约束 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 模块划分、分层依赖、Execution Pipeline、SSE |
| [UI_SPEC.md](docs/UI_SPEC.md) | 页面结构、Execution 展示、交互反馈 |
| [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) | 4 个 Phase、交付物、测试策略、验收方式 |
| [AGENTS.md](AGENTS.md) | 开发 Agent 的硬性约束（红线、审批项、交付要求） |

## 开发环境

| 依赖 | 要求 / 本机实测 |
|---|---|
| Python | 3.14（本机；依赖轮子不可用时可回退 3.11） |
| Node.js / npm | Node 24 + npm 11 |
| Docker | Docker Desktop（Compose 提供 PostgreSQL） |
| Git | 2.54+ |

> 本机 5432 常被其他服务占用，本项目 PostgreSQL 默认映射到 **5433**（可用 `POSTGRES_PORT` / `DATABASE_URL` 调整）。Docker 命令在受限沙箱内不可用。

## 本地运行

```bash
# 1. 数据库
docker compose up -d postgres
docker compose ps                  # 应为 healthy

# 2. 后端（另开终端）
cd backend
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1      # PowerShell
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload      # API 文档：http://127.0.0.1:8000/docs
pytest -q                          # 自动化测试

# 3. 前端（另开终端）
cd frontend
npm install
npm run dev                        # http://localhost:5173
npm run build                      # 类型检查 + 生产构建
```

首次启动时后端会自动创建默认 Workspace；`.env` 可选（复制 `.env.example` 即可，默认值可直接跑通），但 `.env` 永不入库。

## 已实现 API（Phase 1）

| 领域 | 端点 |
|---|---|
| 健康检查 | `GET /api/v1/health` |
| Workspace | `GET /workspaces`、`GET/PATCH /workspaces/{id}` |
| Project | `GET/POST /projects`、`GET/PATCH /projects/{id}`、`GET/POST /projects/{id}/files`、`DELETE /projects/{id}/files/{file_id}` |
| Task | `GET/POST /tasks`、`GET/PATCH /tasks/{id}`（禁止改 project_id，返回 422） |
| File | `POST /files`（multipart）、`GET /files`、`GET/DELETE /files/{id}`、`GET /files/{id}/content` |
| Task 文件上下文 | `GET/POST /tasks/{id}/files`、`DELETE /tasks/{id}/files/{file_id}` |
| 错误格式 | `{"error":{"code":"...","message":"...","details":...}}` |

## 开发路线

| 阶段 | 目标 | 状态 |
|---|---|---|
| Phase 1 | 工程基础与核心数据管理（Workspace / Project / Task / File / 解析 / 继承规则） | 开发中（待人工验收） |
| Phase 2 | Conversation 与模型接入（Provider、流式、模型选择） | 未开始 |
| Phase 3 | Execution 与 Artifact 核心闭环（Pipeline、SSE、版本、快照） | 未开始 |
| Phase 4 | 完整 UI、系统集成与 MVP 验收（Docker、持久化、文档） | 未开始 |

每个 Phase 结束后由用户人工验收，通过后进入下一阶段。开发过程遵循 [AGENTS.md](AGENTS.md)；Git 提交由用户负责。

## 数据与隐私

- 所有资料、数据库与成果默认保存在本机。
- 调用云端模型时只发送本次任务实际需要的上下文，不默认上传整个 Library。
- 模型 API Key 由后端管理，保存在本地受限配置文件，默认掩码显示，不写入日志、不进入 Git。
- 禁止提交 `.env`、`data/`、`storage/` 及任何真实凭证。

## 许可证

未确定。在项目负责人选定许可证前，请勿对外分发或复用本项目代码。
