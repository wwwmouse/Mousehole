# ARCHITECTURE.md — mousehole 系统架构

**文档版本：** v0.2.0-mvp  
**状态：** living（长期维护）  
**最后更新：** 2026-11-23  
**定位：** 当前系统的模块边界、依赖方向、关键数据流与扩展点。只写“为什么/边界/扩展点”，字段与目录细节以代码为准。  
**相关文档：** `ROADMAP.md`（阶段规划）、`DATA_MODEL.md`（数据不变量）、`UI_GUIDE.md`（界面）、`AGENTS.md`（工程约束）。

---

## 1. 系统定位与不变量

mousehole 是面向个人用户的 **Local-first AI Workspace**，采用**模块化单体**，单用户、本地部署优先，前端只通过 REST + SSE 访问后端。

任何阶段都不能破坏的不变量：

1. **分层方向**：`api → service → repository → infrastructure`；模块之间只走公开 Service，Infrastructure 不得反向依赖业务。
2. **Execution 状态唯一来源**：状态只能由 Execution Service 修改；前端只读。
3. **工具受控**：模型只能调用 `TOOLS_SPEC` allowlist 内的工具（当前 4 个），无 Shell、无任意文件系统、无未经确认的外部写；系统提示中的工具说明从 `TOOLS_SPEC` 动态生成。
4. **成果独立**：Artifact 不依赖 Conversation 存在；新版本不覆盖历史；来源可追溯。
5. **上下文显式**：可用上下文 ≠ 实际输入；必须按预算构建，禁止无预算拼接全文。
6. **失败显式**：解析、模型、保存失败必须显式失败并留痕；取消 ≠ 失败。

**单一事实源：** 表结构以 `backend/app/modules/*/models.py` + `alembic/versions/` 为准；API 以 FastAPI 路由/OpenAPI 为准；界面以 `frontend/src` 为准。本文件不复制字段表。

---

## 2. 系统总览

```text
浏览器（Vue 3 + TypeScript）
   │  REST + SSE
   ▼
Nginx（生产）/ Vite dev server（开发）
   │  /api 反向代理
   ▼
FastAPI  app/api/v1（薄层：参数校验 + HTTP/SSE）
   │
   ▼
Service 层  app/modules/*/service.py（业务规则、状态流转、事务）
   │
   ▼
Repository + Infrastructure（SQLAlchemy / 本地存储 / Provider Adapter）
   │
   ▼
PostgreSQL + storage/ + data/
```

部署：生产 `docker compose`（Nginx + backend + PostgreSQL）；开发 `docker-compose.dev.yml`（Vite + FastAPI reload + PostgreSQL）。二者共用数据卷与 storage。

---

## 3. 后端模块

| 模块 | 职责 | 关键入口 |
|---|---|---|
| workspace | 单例 Workspace、默认配置（含 context budget 覆盖） | `modules/workspace/service.py` |
| project | Project CRUD、归档、项目文件关联 | `modules/project/` |
| task | Task CRUD、绑定 Project、删除清理 | `modules/task/` |
| file | 上传、哈希、存储、Library、引用与删除保护、临时文件 | `modules/file/` |
| document | PDF/Markdown/TXT/JSON/YAML/CSV/HTML/CSS 文本提取；不支持格式显式报错 | `modules/document/parsers.py` |
| context | Task 可用文件计算；执行/对话的预算、分批、摘要 | `modules/context/builder.py` |
| conversation | Conversation/Message、Chat 上下文、SSE、受控工具 pre-pass | `modules/conversation/`、`api/v1/chat.py` |
| model | Provider 配置、模型解析、流式/非流式调用、usage | `modules/model/` |
| execution | 状态机、进程内 Scheduler、确定性 Pipeline、事件总线、快照 | `modules/execution/` |
| artifact | ArtifactSeries + 版本、来源、下载/删除 | `modules/artifact/` |
| skill | 全局 Skill Library、Skill 文件、Task 引用 | `modules/skill/` |
| stats | Home 只读统计 | `modules/stats/` |

API 层：`app/api/v1/` 下按资源拆分（workspaces、projects、tasks、task_files、chat、executions、artifacts、files、skills、stats、providers、models、health），路由汇总在 `api/v1/router.py`。

---

## 4. 关键流程

### 4.1 Chat（含受控工具）

1. `POST /api/v1/tasks/{id}/messages`（SSE）→ 校验 Task、解析模型与参数、加载历史。
2. 根据意图开关/关键词决定是否进入工具 pre-pass（非流式，最多 4 轮）。
3. 模型可调用 `read_task_files` / `read_task_file` / `save_artifact` / `create_execution`；后端 allowlist 校验并执行，结果回灌。
4. 最终回答统一走流式生成；期间发送 `thinking` 心跳避免“假死”观感。
5. 持久化 Message（含 usage、工具步骤、引用文件/Skill 的 metadata）。
6. 不支持的模型自动回退为普通流式对话；工具失败显式返回错误。

### 4.2 Execution（确定性 Pipeline）

| 顺序 | 阶段 | 职责 |
|---|---|---|
| 1 | resolve_files | 解析 Task 可用文件（继承 + 额外 − 排除） |
| 2 | parse_documents | 提取文本（含 Skill 资料） |
| 3 | build_context | 预算、分批、摘要，产出实际输入 |
| 4 | model_call | 调用模型（网络/超时类错误重试一次） |
| 5 | generate_artifact | 组织 Markdown 成果 |
| 6 | save_artifact | 保存 Artifact + 来源 + 快照 |
| 7 | complete | 更新状态 |

- Scheduler：进程内 FIFO，默认并发 2（`main.py` 注入）；启动时恢复 pending，把僵死 running 标记 failed。
- 每步写入 `execution_steps`（状态、摘要、时间），并通过 SSE 推送。
- `execution_file_snapshots` 记录实际参与的文件、直接/摘要模式与内容 hash。
- 同一 Task 的 Execution 用 `sequence` 递增；重跑产生新 Execution，不覆盖历史。

### 4.3 上下文构建

- 可用文件 = Project 继承文件 ∪ Task 额外引用 − Task 排除；临时文件仅在当前一轮 Chat 生效。
- 预算按模型窗口推导（扣除输出与开销预留），未知模型回退 32k；Workspace 可覆盖。
- 超预算：分批 + 每批摘要 + 汇总；只对实际参与的文件写快照，并标注 `direct` / `summarized`。
- Chat 默认读取全文（≤2MB/文件），总预算默认 64k；超预算才截断并提示用 `read_task_file` 分页。

### 4.4 模型接入

- Provider Adapter：OpenAI 兼容（OpenAI/DeepSeek）、Ollama；统一 `stream_chat` / `complete` 与错误归一化。
- 配置存 `data/provider_config.json`（明文，不入 Git）；接口只返回掩码；API Key 不写日志。
- 每次调用记录 usage（Provider 提供时）；Execution 记录模型/参数快照。

---

## 5. 状态、失败与恢复

### 5.1 Execution 状态

```text
pending ──► running ──► completed
                │
                ├──► failed
                └──► cancelled
```

- `cancelled` 是协作式取消（Pending 直接取消，Running 在检查点停止），**不是失败**。
- 重启后：pending 重新排队；running 统一标记 failed 并写原因；不实现断点续跑。
- Artifact 保存失败 → Execution 不得标记 completed。

### 5.2 SSE 事件

- Chat：`thinking` / `tool_call` / `tool_result` / `delta` / `done` / `error`。
- Execution：`step.started` / `step.completed` / `step.failed` / 执行终态事件。
- SSE 断开后，前端重新拉取最新状态，而不是直接判定失败。

### 5.3 错误处理

统一异常类型 + 错误码；用户可见错误与调试日志分离；日志不写 Key、文件全文、Prompt 全文（Phase 5 补日志脱敏机制）。

---

## 6. 安全边界

- 工具只操作**当前 Task** 的可用文件/成果/执行；无任意文件系统、Shell、外部写。
- 单用户本地部署，无登录/权限系统；部署边界即安全边界。
- 前端不得直连数据库或模型供应商；所有业务规则在后端。
- 删除文件/成果前做引用检查（被引用时返回 409），避免破坏历史。

---

## 7. 扩展点（加功能先看这里）

| 扩展 | 修改位置 | 注意 |
|---|---|---|
| 新 Provider | `model/config.py` + `model/adapters.py` | OpenAI 兼容通常只加配置；新协议才写 Adapter |
| 新文件解析器 | `document/service.py`、`parsers.py`、`file/service.py` 允许类型、`utils/fileTypes.ts` | 不支持的格式必须显式报错；新依赖需批准 |
| 新受控工具 | `conversation/tools.py` 的 `TOOL_SPECS` + dispatch + 动态提示 | 同步 Chat 意图判断；不得突破 allowlist |
| 新 Pipeline 阶段 | `execution/pipeline.py`（阶段顺序硬编码）、`services` | `step_type` 为自由字符串；前端 SSE 通用 |
| 新 Artifact 类型 | `artifact/models.py` 的 `content_type`/`storage_key` + 下载/预览分支 | 文本类成本低；二进制需改存储与预览 |
| 新页面 | `frontend/src/router`、`AppShell`、`api/endpoints.ts` | 页面组件不写复杂业务 |
| 新搜索/索引 | Phase 5 起新增只读 `search` 模块 | 先 ILIKE/索引，不引入外部搜索引擎 |

---

## 8. Phase 5 规划增量（未实现）

> 阶段规格见 `ROADMAP.md` §4；数据增量见 `DATA_MODEL.md` §5；界面见 `UI_GUIDE.md` §6。

- **ContextItem 抽象**：文件 / 成果 / Skill 资料统一参与预算、排序、截断；执行写入 `context_manifest`（只存清单与 token，不存全文）。
- **成果复用**：Task 引用 Artifact（钉版本），Chat 与 Execution 均可纳入上下文；新增引用表与执行快照表。
- **解析线程化**：PDF/文本解析移出事件循环（线程池 + 超时），避免阻塞 API/SSE。
- **只读搜索模块**：聚合 Project/Task/File/Artifact/Message。
- **日志与配置**：统一 logging + 脱敏过滤器；并发/预算/模型窗口配置化。
- **前端**：全局 Artifacts 页、运行卡、上下文查看器、Diff、⌘K、模板、对话上下文管理。

边界：不引入 RAG/向量库/embedding、消息队列、多 Agent、多用户；不改变确定性 Pipeline 与 allowlist。

---

## 9. 代码导航

| 位置 | 内容 |
|---|---|
| `backend/app/api/v1/` | HTTP/SSE 端点（薄层） |
| `backend/app/modules/` | 12 个业务模块（见 §3） |
| `backend/app/core/`、`shared/` | 配置、异常、枚举、usage、默认值 |
| `backend/app/infrastructure/` | SQLAlchemy Base/Session |
| `backend/alembic/versions/` | 迁移（当前 head `n4o5p6q7r8s9`） |
| `backend/tests/` | 107 个 pytest（v0.2.0-mvp） |
| `frontend/src/views/` | 页面（TaskView 较大，Phase 5 计划拆分） |
| `frontend/src/components/` | ChatPanel、RunProgress、TaskArtifacts、FilePreviewModal 等 |
| `frontend/e2e/` | Playwright 核心闭环（Mock API） |
| `scripts/` | `backup.ps1`、`restore.ps1` |

---

## 10. 已知限制（v0.2.0-mvp）

- 进程内 Scheduler：单实例；重启后 running 标记 failed，无断点续跑。
- 解析在 async Pipeline 内同步执行（Phase 5 H1 修复），大文件可能阻塞。
- 测试跑 SQLite 内存库；Postgres 迁移未被自动化覆盖（Phase 5 H3 修复）。
- 无日志脱敏配置；Chat 失败不落库（Phase 5 H2/F10 修复）。
- 无 RAG/向量检索；上下文靠显式预算 + 摘要。
- 无多用户/权限/协作；无移动端。
- `TaskView.vue`、`ChatPanel.vue` 偏大，前端无单测（Phase 5 H7 改善）。
