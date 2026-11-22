# AGENTS.md — mousehole 开发约束

> 本文件约束一切在本仓库工作的 AI Coding Agent（含多 Agent 协作的 Lead 与 Teammate）。
> 优先级：设计文档 > 本文件 > 你的个人习惯。发现冲突先提出，不要自行取舍。

## 1. 项目本质（先记住这一句）

mousehole 是**面向个人用户的 Local-first AI Workspace**，不是聊天客户端，也不是 Agent 平台。
骨架：Workspace → Project → Task → Execution → Artifact；File 提供资料，Conversation 记录交流。
MVP 只验证一条闭环：建 Project → 传多份文档 → 建 Task → AI 分析 → 存 Markdown Artifact → 重启后仍可复用。

当前状态：Phase 1–4 已完成并通过 MVP 功能验收（统计/Overview/筛选/运行历史、Docker 生产/开发栈、备份恢复、Playwright E2E、文件预览、SSE 流式与临时文件单轮化；2026-11-22 完成 All Tasks / Task 左树 / Projects Ledger / 状态色与字体统一等 UI 收尾）。
当前处于 MVP 冻结与发布收尾阶段，准备打 tag；下一个交付点 = 用户决定 Phase 5 范围。

## 2. 开工前必读（按顺序）

1. `docs/MVP_SPEC.md`：本轮做什么、不做什么。
2. `docs/DATA_MODEL.md`：实体、字段、关系、删除规则。
3. `docs/TECHNICAL_DECISIONS.md`：技术栈与工程约束。
4. `docs/ARCHITECTURE.md`：模块职责、依赖方向、Execution Pipeline。
5. `docs/UI_SPEC.md`：页面结构与交互。
6. `docs/DEVELOPMENT_PLAN.md`：当前 Phase 的交付物与验收。

只做当前 Phase 的事。不属于本 Phase 的"顺手改进"一律不做，最多记入待办。

## 3. 不可自行决定（先提案，等用户确认）

- 更换既定技术栈（Vue 3 / FastAPI / PostgreSQL / SSE / 进程内 Scheduler）；
- 修改核心实体、字段、关系或状态枚举；
- 调整模块职责、依赖方向、分层规则；
- 扩大或缩小 MVP 范围；
- 引入大型依赖或新基础设施（消息队列、缓存、向量库、组件库、ORM 变更等）；
- 执行 `git commit` / `push` / 切分支 / 改远程仓库（Git 只读，改动留在工作区）。

## 4. 硬性红线

1. 失败不得伪装成功：解析失败、模型失败、保存失败必须显式失败并留痕。
2. 不得静默跳过文件或错误；不支持的格式必须给明确错误。
3. Conversation 不得承载执行记录或成果；Artifact 独立保存，新版本不覆盖历史。
4. 文件只存一份：存储与引用分离，上传到 Library ≠ 所有 Task 可读。
5. 可用上下文 ≠ 实际输入：禁止无预算地把文件全文拼进 Prompt。
6. 前端不得直连数据库或模型供应商；所有业务规则在后端。
7. API Key、完整文件内容、Prompt 全文不得写入日志；`.env`、`data/`、`storage/` 不入 Git。
8. Execution 状态只能由 Execution Service 修改，前端只读。
9. 模型可调用的工具必须走 TOOLS_SPEC allowlist 执行，禁止任意文件系统、Shell、外部写操作；系统提示里的工具说明必须从 TOOLS_SPEC 动态生成，不得硬编码。

## 5. 代码与工程约定

- 后端分层：api → service → repository → infrastructure；模块间只走公开 Service，禁止跨模块引用内部实现，禁止 Infrastructure 反向依赖业务。
- 前端：页面组件不写复杂业务；HTTP 统一封装；Pinia 只放跨页共享状态；桌面优先、暗色单主题、不做移动端。
- Python 3.14 + pydantic v2 + SQLAlchemy 2.x；所有表结构变化必须走 Alembic 迁移。
- 主键 UUID v4；枚举用 VARCHAR + CHECK 约束；时间统一 UTC。
- 每个模块：类型注解 + 统一异常 + 单元测试；核心规则（文件继承、状态流转、版本号、删除引用检查）必须有测试。
- 多 Agent 并行时按目录划分写权限（例如 `frontend/` 与 `backend/` 由不同成员负责），同一文件不要两人同时修改。

## 6. 每个交付点的必交内容

功能清单 / 主要变更 / DB 迁移 / API 与前端说明 / 测试结果（贴真实输出）/ 未解决问题 / 已知风险 / 人工验收步骤。
未跑通、未验证的功能不得写成"已完成"。

## 7. 验证方式

- 前端：`npm run dev` 能打开核心页面。
- 后端：`pytest` 通过；`uvicorn` 可启动；`/api/v1/health` 正常。
- 数据：`alembic upgrade head` 成功；重启后数据仍在。
- 部署：`docker compose up` 可启动（Docker 命令需非沙箱执行）。

## 8. 遇到歧义

设计文档 → 最小实现（不扩范围）→ 在阶段交付说明中记录取舍。
仍不确定就提问，不要猜；不要用代码反向覆盖设计决策。
