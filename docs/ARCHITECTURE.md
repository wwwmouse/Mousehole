# ARCHITECTURE.md — mousehole 系统架构

**文档版本：** v0.3.0（Phase 6 进行中）  
**状态：** living（长期维护）  
**最后更新：** 2026-11-26  
**定位：** 当前系统的整体结构、仓库职责、四层技术边界与模块衔接方式。字段级细节以代码与迁移为准。  
**相关文档：** `ROADMAP.md`（阶段规划）、`DATA_MODEL.md`（数据不变量）、`UI_GUIDE.md`（界面）、`AGENTS.md`（工程约束）。

---

## 1. 系统定位与不变量

mousehole 是面向个人用户的 **Local-first AI Workspace**，采用**模块化单体**：单用户、本地部署优先，前端只通过 REST + SSE 访问后端。

任何阶段都不能破坏的不变量：

1. **分层方向**：`api → service → repository → infrastructure`；模块之间优先走公开 Service，Infrastructure 不得反向依赖业务。
2. **Execution 状态唯一来源**：状态只能由 Execution Service 修改；前端只读。
3. **工具受控**：模型只能调用 `TOOLS_SPEC` allowlist 内的工具（当前 4 个），无 Shell、无任意文件系统、无未经确认的外部写。
4. **成果独立**：Artifact 不依赖 Conversation 存在；新版本不覆盖历史；来源可追溯。
5. **上下文显式**：可用上下文 ≠ 实际输入；必须按预算构建，禁止无预算拼接全文。
6. **失败显式**：解析、模型、保存失败必须显式失败并留痕；取消 ≠ 失败。

**单一事实源：** 表结构以 `backend/app/modules/*/models.py` + `backend/alembic/versions/` 为准；API 以 FastAPI 路由/OpenAPI 为准；界面以 `frontend/src` 为准。

---

## 2. 整体架构

### 2.1 运行时拓扑

```text
浏览器（Vue 3 SPA）
   │  REST + SSE（/api/v1）
   ▼
Nginx（生产） / Vite dev server（开发）
   │  反向代理
   ▼
FastAPI（backend/app/api/v1）
   │
   ├── Service 层（业务规则/事务）
   │      ├── Repository → SQLAlchemy → PostgreSQL
   │      ├── File/Storage → storage/（内容寻址）
   │      └── Model Adapter → OpenAI / DeepSeek / Ollama
   │
   └── OCR 任务线程（进程内）
          ├── PyMuPDF：PDF 页路由与渲染
          └── Qwen3-VL（Ollama OpenAI 兼容接口）：页图 OCR
```

### 2.2 部署形态

- **生产**：`docker compose` 启动 frontend（Nginx）、backend、PostgreSQL。
- **开发**：`docker-compose.dev.yml` 启动 Vite dev server、FastAPI reload、PostgreSQL。
- **本地数据**：`data/`（配置）、`storage/`（文件字节）、PostgreSQL 数据卷。
- **模型**：DeepSeek/OpenAI 走外网；Ollama/Qwen3-VL 跑宿主机，容器通过 `host.docker.internal` 访问。
- **单实例假设**：进程内 Scheduler、进程内 OCR 任务线程；不做多副本调度。

---

## 3. 仓库地图

```text
mousehole/
├── backend/                 FastAPI 后端
│   ├── app/
│   │   ├── api/v1/           HTTP/SSE 路由（薄层）
│   │   ├── modules/          领域模块（业务规则）
│   │   ├── core/             配置、日志
│   │   ├── shared/           异常、枚举、usage、DB 类型
│   │   └── infrastructure/   SQLAlchemy Base/Session/模型注册
│   ├── alembic/              数据库迁移
│   ├── tests/                pytest
│   └── requirements.txt
├── frontend/                Vue 3 前端
│   ├── src/api/             HTTP/SSE 客户端与 DTO
│   ├── src/views/           页面
│   ├── src/components/      组件
│   ├── src/composables/     流式/执行等组合逻辑
│   ├── src/stores/          Pinia 跨页状态
│   ├── src/router/          路由
│   ├── src/styles/          设计 token 与全局 CSS
│   ├── src/utils/           格式化、SSE、Markdown、文件类型
│   ├── tests/unit/          Vitest
│   └── e2e/                 Playwright
├── scripts/                 OCR CLI、备份/恢复、测试脚本
├── docs/                    ROADMAP / ARCHITECTURE / DATA_MODEL / UI_GUIDE
├── data/                    Provider 配置等本地数据（不入 Git）
├── storage/                 文件内容寻址存储（不入 Git）
├── docker-compose*.yml
├── .env.example             运行环境模板（真实 .env 不入 Git）
├── README.md
└── AGENTS.md
```

---

## 4. 四层架构

### 4.1 前端层（Vue 3 SPA）

**技术栈 / SDK**

| 技术 | 用途 |
|---|---|
| Vue 3.5 + TypeScript | 页面与组件 |
| Vite 6 | 开发/构建 |
| Vue Router 4 | 页面路由 |
| Pinia 2 | 跨页共享状态 |
| 原生 `fetch` | HTTP 请求（未使用 Axios） |
| 自定义 `utils/sse.ts` | 解析 SSE 帧（Chat/执行） |
| Vitest 5 + Playwright | 单测与 E2E |
| 原生 CSS 变量 | 主题与组件样式（不引入组件库） |

**文件位置**

- 页面：`frontend/src/views/`（Home、Tasks、Task、Projects、ProjectDetail、Library、Skills、Settings）
- 路由：`frontend/src/router/index.ts`
- 壳层：`frontend/src/components/AppShell.vue`
- 页面组件：`frontend/src/components/`（ChatPanel、TaskArtifacts、FilePreviewModal、RunProgress 等）
- API 客户端：`frontend/src/api/client.ts`（base URL、超时、错误归一化）
- API 方法：`frontend/src/api/endpoints.ts`
- Chat SSE：`frontend/src/api/chat.ts` + `frontend/src/composables/useChatStream.ts`
- 执行进度：`frontend/src/composables/useExecutionProgress.ts`
- 类型：`frontend/src/api/types.ts`
- 全局状态：`frontend/src/stores/app.ts`

**核心边界**

- 页面不直连数据库/模型供应商，只调用 `api/endpoints.ts`。
- SSE 断开后重新拉取状态，不把断流直接判定为失败。
- 组件不写业务规则；纯逻辑放 `utils/` 或 `composables/`。

---

### 4.2 后端层（FastAPI + 模块化单体）

**技术栈 / SDK**

| 技术 | 用途 |
|---|---|
| Python 3.14 | 运行时 |
| FastAPI + Uvicorn | HTTP/SSE 服务 |
| Pydantic v2 | API DTO 与校验 |
| SQLAlchemy 2.x（同步） | ORM |
| Alembic | 迁移 |
| PostgreSQL + pg8000 | 数据库 |
| httpx | Provider / Ollama / VLM HTTP 调用（无官方 SDK） |
| PyMuPDF | PDF 路由、页文本、页图渲染 |
| pypdf | 旧 PDF 文本提取路径 |
| python-multipart | 文件上传 |
| pytest + TestClient | 测试 |

**分层**

```text
api/v1/*.py
  ↓ 调用公开 Service
modules/*/service.py
  ↓ 调用 Repository / 其他模块公开 Service
modules/*/repository.py
  ↓ ORM
infrastructure/database + modules/*/models.py
  ↓
PostgreSQL
```

**模块职责**

| 模块 | 职责 | 关键文件 |
|---|---|---|
| workspace | 单例 Workspace、默认配置 | `modules/workspace/` |
| project | Project CRUD、归档、项目文件关联 | `modules/project/` |
| task | Task CRUD、Project 绑定、删除清理 | `modules/task/` |
| file | 上传、哈希、存储、Library、引用保护、项目私有文件 | `modules/file/` |
| document | 文本解析、PDF 页级路由、VLM OCR 客户端/编排 | `modules/document/` |
| ocr | `file_pages` / `ocr_jobs` 持久化与任务执行 | `modules/ocr/` |
| context | Task 可用文件、预算、分批、摘要 | `modules/context/` |
| conversation | Conversation/Message、Chat 上下文、受控工具、一轮对话编排 | `modules/conversation/` |
| model | Provider 配置、模型解析、流式/非流式调用、usage | `modules/model/` |
| execution | 状态机、Scheduler、确定性 Pipeline、快照 | `modules/execution/` |
| artifact | 成果系列/版本、来源、下载/删除 | `modules/artifact/` |
| skill | Skill Library、文件附件、Task 引用 | `modules/skill/` |
| stats | Home 只读统计 | `modules/stats/` |

**核心入口**

- 应用装配：`backend/app/main.py`
- 配置：`backend/app/core/config.py`
- 日志/request-id：`backend/app/core/logging.py`
- 统一异常：`backend/app/shared/exceptions.py`
- DB Session：`backend/app/infrastructure/database/session.py`
- 模型注册：`backend/app/infrastructure/database/models.py`

---

### 4.3 API 层（REST + SSE）

**约定**

- 前缀：`/api/v1`
- 普通接口：JSON；错误统一为：

```json
{"error": {"code": "not_found", "message": "文件不存在", "details": null}}
```

- 流式接口：`text/event-stream`（Chat、Execution 进度）
- 无登录/权限系统；部署边界即安全边界。
- 请求带 `X-Request-ID`，日志脱敏。

**路由文件**

| 文件 | 资源 |
|---|---|
| `api/v1/router.py` | 路由汇总 |
| `api/v1/workspaces.py` | Workspace |
| `api/v1/projects.py` | Project、项目文件 |
| `api/v1/tasks.py` | Task |
| `api/v1/task_files.py` | Task 文件上下文/临时文件 |
| `api/v1/files.py` | Library 文件、原始字节预览、内容读取 |
| `api/v1/chat.py` | Chat HTTP/SSE 适配（编排在 `modules/conversation/chat_turn.py`） |
| `api/v1/executions.py` | Execution 创建/查询/SSE |
| `api/v1/artifacts.py` | Artifact/Series、下载、存入 Library |
| `api/v1/skills.py` | Skill Library |
| `api/v1/providers.py` | Provider 配置/测试 |
| `api/v1/models.py` | 可选模型 |
| `api/v1/stats.py` | Home 统计 |
| `api/v1/health.py` | 健康检查 |
| `api/v1/ocr.py` | 页面准备任务、页级文本 |

**Phase 6 OCR API（已实现）**

```http
POST /api/v1/files/{file_id}/ocr       # 创建页面准备任务
GET  /api/v1/files/{file_id}/ocr       # 最新任务/进度/摘要
GET  /api/v1/files/{file_id}/pages     # 页级文本分页
```

任务响应包含 `current_page / native_pages / ocr_pages / image_coverage / route`，供前端展示“正在读取哪一页”和完成后的思维链总结。

---

### 4.4 数据库与存储层

**技术栈**

- PostgreSQL；UUID 主键；枚举用 VARCHAR + CHECK；时间统一 UTC。
- SQLAlchemy 2.x 同步 Session；pg8000 驱动。
- Alembic 迁移；每个迁移提供 downgrade。
- 文件字节：`storage/` 内容寻址（`storage/objects/...`），数据库只保存 `storage_key`、hash、大小。
- Provider 配置：`data/provider_config.json`；环境配置：`.env`。

**数据分组**

| 组 | 表 |
|---|---|
| 组织 | `workspaces`、`projects`、`tasks` |
| 文件 | `files`、`project_files`、`task_file_overrides`、`file_pages`、`ocr_jobs` |
| 对话 | `conversations`、`messages` |
| 执行 | `executions`、`execution_steps`、`execution_file_snapshots` |
| 成果 | `artifact_series`、`artifacts` |
| 能力 | `skills`、`skill_files`、`task_skills` |

**关键规则**

- 一个 Task 一个 Conversation；`context_start_sequence` 只影响 Chat 发送给模型的历史，不删除消息。
- Artifact 版本只追加；`current_artifact_id` 只是指针。
- File 只存一份；上传 Library ≠ 所有 Task 可读；项目私有文件 `is_temporary + owner_project_id`。
- `file_pages` 是 PDF 派生文本；`ocr_jobs` 记录页面准备任务状态。
- 文档删除/项目删除时按引用规则清理；历史快照仍引用的文件保留。

---

## 5. 核心链路

### 5.1 Chat（SSE + 受控工具）

```text
ChatPanel
→ useChatStream
→ api/chat.ts
→ POST /tasks/{id}/messages
→ api/v1/chat.py（HTTP/SSE 适配）
→ conversation.chat_turn（一轮编排）
→ conversation service（历史边界、Skill/文件上下文）
→ work 模式：工具 pre-pass
   → read_task_files / read_task_file / save_artifact / create_execution
→ model stream → 结构化事件
→ chat.py 转 SSE delta
→ Message + metadata 落库
→ done（usage / artifacts / executions）
```

关键点：

- 对话模式无工具；工作模式工具由模型决定。
- 历史只取 `context_start_sequence` 之后、最近 `CHAT_HISTORY_LIMIT` 条。
- 工具失败显式回传，不伪装成功。

### 5.2 Execution（确定性 Pipeline）

```text
TaskView / RunProgress
→ POST /tasks/{id}/executions
→ execution service + scheduler
→ pipeline:
   resolve_files → parse_documents → build_context
   → model_call → generate_artifact → save_artifact → complete
```

依赖模块：`context`、`document`、`file`、`model`、`artifact`、`skill`、`task`。  
Execution 状态只由 `execution/service.py` 修改，SSE 只做进度通知。

### 5.3 文件 / 项目 / OCR

```text
LibraryView / ProjectDetail / FilePreviewModal
→ /api/v1/files、/api/v1/projects/{id}/files
→ file service：
   上传 → 存储 → File 行 → ProjectFile/TaskFileOverride
   项目私有文件：is_temporary + owner_project_id；不进入 Library

PDF 页准备：
→ POST /files/{id}/ocr
→ ocr service：
   document.pdf_router（页级图像覆盖率）
   → text 页：PyMuPDF 提取
   → OCR 页：PyMuPDF 渲染 → vlm_ocr（Qwen3-VL）
   → file_pages 落库 + ocr_jobs 进度
→ GET /files/{id}/pages
→ GET /files/{id}/content 优先返回页文本
```

### 5.4 Artifact / Skill / Library

```text
TaskArtifacts
→ /artifact-series、/artifacts
→ artifact service（版本、current 指针、来源）
→ 存入 Library：artifact service → file service（内容寻址复用）

SkillsView / Chat +
→ skill service（Skill 定义、文件附件、Task 引用）
```

---

## 6. 模块之间如何衔接

### 6.1 衔接机制

| 机制 | 使用位置 | 说明 |
|---|---|---|
| REST DTO | 前端 ↔ API | `frontend/src/api/types.ts` 与 Pydantic schema 对齐 |
| SSE 事件 | Chat / Execution | 前端解析事件，不把断流当失败 |
| 公开 Service 调用 | 后端模块之间 | 业务规则只在 Service，API 不跨模块写规则 |
| Repository + SQLAlchemy | Service → DB | 跨模块查询优先走目标模块公开 Service |
| 文件存储 | File/OCR/Artifact | 内容寻址，数据库只存 key/hash |
| JSON metadata | Message / usage | 工具步骤、文件/Skill 引用、usage 等松散扩展数据 |
| 统一异常 | API ↔ 前端 | `AppError` 映射为错误 envelope |
| 轮询 | OCR 前端 | `GET /files/{id}/ocr` 获取进度/当前页 |

### 6.2 依赖方向

```text
api/v1
  ├── conversation ──→ context / file / skill / artifact / execution / model
  ├── execution ─────→ context / document / file / model / artifact / skill / task
  ├── ocr ───────────→ document / file / storage
  ├── project ───────→ file / task / workspace
  ├── artifact ──────→ file（导出到 Library）
  └── task ──────────→ artifact / execution / file / conversation（删除清理）
```

规则：

- API 只做参数校验、调用 Service、返回 DTO。
- Service 负责事务、状态机、引用检查。
- Repository 不跨模块直接互相调用；跨模块业务通过公开 Service。
- 前端类型与后端 Schema 分开维护，但字段必须一致。
- 任何新功能先判断属于哪个模块，避免在 API 层堆业务逻辑。

---

## 7. 状态、失败与安全

### 7.1 状态

- Execution：`pending → running → completed / failed / cancelled`；取消 ≠ 失败。
- OCR Job：`pending → running → completed / failed`；重启后残留任务标记 failed。
- Artifact：版本只追加；current 指针移动，不覆盖历史。

### 7.2 失败

- 解析失败：显式 `FileParseError`；空文本不伪装成功。
- 模型失败：`ProviderError`；前端显示错误。
- 保存失败：不把 Execution 标记 completed。
- 前端 SSE 断开：重新拉取状态，不直接判定失败。

### 7.3 安全

- 工具只访问当前 Task 的可用文件/成果/执行。
- 无 Shell、无任意文件系统、无外部写。
- API Key 只存 `data/provider_config.json`；日志不写 Key/全文/Prompt。
- 单用户本地部署；无登录/权限系统。
