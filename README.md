# mousehole

> 面向个人用户的 **Local-first AI Workspace**：把资料、任务、执行过程和成果沉淀在同一个持续存在的工作空间里。

**当前状态：Phase 2 已完成（已验收）。** Phase 1（工作空间/项目/任务/文件/解析）与 Phase 2（对话与模型接入：Conversation/Message、DeepSeek/OpenAI/Ollama、SSE 流式、Token usage、模型参数）均已实现并通过自动化测试与人工验收。下一步进入 **Phase 3：Execution 与 Artifact 核心闭环**。

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

> 需要**三个终端**：数据库（Docker）、后端（Python）、前端（Node），三者互相独立。
> 常见误区：`alembic upgrade head` 只是升级数据库表结构，**不是启动后端**；后端由 `uvicorn` 启动，前端由 `npm run dev` 启动。

### 前置安装（只需一次）

```powershell
# 后端依赖
cd E:\VScode\Mousehole\backend
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 前端依赖
cd ..\frontend
npm install
```

### 终端 1：数据库

```powershell
cd E:\VScode\Mousehole
docker compose up -d postgres
docker compose ps                  # 看到 healthy 即可
```

### 终端 2：后端

```powershell
cd E:\VScode\Mousehole\backend

# ① 升级数据库结构（有新增/修改表时执行一次；不是启动服务）
.\.venv\Scripts\python.exe -m alembic upgrade head

# ② 启动后端 API（这一步才是“启动后端”）
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
# API 文档：http://127.0.0.1:8000/docs
# 健康检查：http://127.0.0.1:8000/api/v1/health
```

### 终端 3：前端

```powershell
cd E:\VScode\Mousehole\frontend
npm run dev                        # http://localhost:5173（Vite 代理 /api 到后端）
# 生产构建预览：npm run build; npm run preview
```

### 常用命令

| 目的 | 命令 |
|---|---|
| 后端测试 | `cd backend; .\.venv\Scripts\python.exe -m pytest tests -q` |
| 前端类型检查 + 构建 | `cd frontend; npm run build` |
| 升级数据库结构 | `cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head` |
| 查看当前迁移版本 | `cd backend; .\.venv\Scripts\python.exe -m alembic current` |

首次启动时后端会自动创建默认 Workspace；`.env` 可选（复制 `.env.example` 即可，默认值可直接跑通），但 `.env` 永不入库。

## 已实现 API（Phase 1 + Phase 2）

| 领域 | 端点 |
|---|---|
| 健康检查 | `GET /api/v1/health` |
| Workspace | `GET /workspaces`、`GET/PATCH /workspaces/{id}` |
| Project | `GET/POST /projects`、`GET/PATCH /projects/{id}`、`GET/POST /projects/{id}/files`、`DELETE /projects/{id}/files/{file_id}` |
| Task | `GET/POST /tasks`、`GET/PATCH /tasks/{id}`（禁止改 project_id，返回 422） |
| File | `POST /files`（multipart）、`GET /files`、`GET/DELETE /files/{id}`、`GET /files/{id}/content` |
| Task 文件上下文 | `GET/POST /tasks/{id}/files`、`DELETE /tasks/{id}/files/{file_id}` |
| 对话（Phase 2） | `GET /tasks/{id}/messages`、`POST /tasks/{id}/messages`（SSE 流式） |
| 模型 Provider | `GET/PUT /providers`、`POST /providers/{name}/test`（测试连接并自动发现模型） |
| 模型列表 | `GET /models` |
| 错误格式 | `{"error":{"code":"...","message":"...","details":...}}` |

## 模型配置（Phase 2）

1. 打开前端 **Settings** 页；
2. 展开 `deepseek` / `openai` / `ollama` 卡片（点击标题行箭头）；
3. 云端 Provider 填 API Key；Ollama 确认 Base URL 后保存即启用；
4. 点 **测试连接**：成功后会**自动发现该 Provider 实际可用的模型列表**；
5. 到 **Task → Settings → 模型配置** 选择模型，并可设置 Temperature / Max tokens；
   留空则使用 Settings 页 **模型默认参数** 中的工作空间默认值。

> 模型选择是 **按 Task 生效**（切换只影响之后的调用）；密钥保存在本机 `data/provider_config.json`，接口只返回掩码，不写入日志、不入 Git。

## 已实现能力

**Phase 1 — 工作组织与资料**
- Workspace / Project / Task 的创建、编辑、归档、删除（三点菜单）
- Global Library 文件上传（PDF / Markdown / TXT）、解析、内容预览、软删除与引用保护（409）
- Project 文件关联；Task 文件上下文：项目继承 + 额外引用 + 排除

**Phase 2 — 对话与模型接入**
- Task 内 Chat：消息持久化、SSE 流式输出、错误反馈、停止生成
- Conversation / Message 模型；Task 1:1 会话
- Provider 配置（DeepSeek / OpenAI / Ollama），密钥本地保存、接口只返回掩码
- 「测试连接」自动发现可用模型（DeepSeek 为 `deepseek-flash` / `deepseek-v4-pro`）
- Task 级模型选择与 Temperature / Max tokens；Workspace 级默认参数
- Token usage：Message 单次记录 → Task 累计 → Chat 顶部显示（Project 维度汇总统计留待后续版本）

## 开发路线

| 阶段 | 目标 | 状态 |
|---|---|---|
| Phase 1 | 工程基础与核心数据管理（Workspace / Project / Task / File / 解析 / 继承规则） | 已完成（已验收） |
| Phase 2 | Conversation 与模型接入（Provider、流式、模型选择、usage） | 已完成（已验收） |
| Phase 3 | Execution 与 Artifact 核心闭环（Pipeline、SSE、版本、快照） | 下一步 |
| Phase 4 | 完整 UI、系统集成与 MVP 验收（Docker、持久化、文档） | 未开始 |

每个 Phase 结束后由用户人工验收，通过后进入下一阶段。开发过程遵循 [AGENTS.md](AGENTS.md)；Git 提交由用户负责。

## 数据与隐私

- 所有资料、数据库与成果默认保存在本机。
- 调用云端模型时只发送本次任务实际需要的上下文，不默认上传整个 Library。
- 模型 API Key 由后端管理，保存在本地受限配置文件，默认掩码显示，不写入日志、不进入 Git。
- 禁止提交 `.env`、`data/`、`storage/` 及任何真实凭证。

## 许可证

未确定。在项目负责人选定许可证前，请勿对外分发或复用本项目代码。
