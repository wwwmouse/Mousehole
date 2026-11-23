# ROADMAP.md — mousehole 演进路线（MVP 之后）

**文档版本：** v0.2.0-mvp  
**状态：** living（长期维护）  
**基线：** v0.2.0-mvp（Phase 1–4 已完成）  
**定位：** MVP 之后**所有阶段（Phase 5、6、7…）的唯一规划与验收入口**。一个阶段 = 本文一个章节，**不再为单个 Phase 新建文档**。  
**上游：** `archive/mvp/PRODUCT_SPEC.md`（产品愿景，已归档）、`archive/mvp/MVP_SPEC.md`（MVP 范围，已归档）、`archive/mvp/DEVELOPMENT_PLAN.md`（Phase 1–4 记录，已归档）  
**下游：** `AGENTS.md`（当前阶段约束）、`README.md`（入口）；系统细节见 `ARCHITECTURE.md` / `DATA_MODEL.md` / `UI_GUIDE.md`。

---

## 0. 文档分工与使用规则

### 0.1 文档分层与职责

| 层 | 文档 | 角色 | 是否修改 |
|---|---|---|---|
| 冻结层（MVP 历史） | `archive/mvp/` 下的 `PRODUCT_SPEC.md`、`MVP_SPEC.md`、`TECHNICAL_DECISIONS.md`、`DEVELOPMENT_PLAN.md` | MVP 期的产品定义、范围、技术选型与交付记录 | **只读**，不再写入新内容 |
| 现状层（技术） | `ARCHITECTURE.md`、`DATA_MODEL.md`、`UI_GUIDE.md` | 当前系统的架构、数据模型、页面与交互 | 持续维护：当前系统 + 已确认的下一阶段技术增量（标注"未实现"）；交付后转为"Phase N 实装补充" |
| 演进层（本文） | `ROADMAP.md` | 阶段目标、范围、关键决策、里程碑、验收、发布记录、Backlog | 长期维护：每阶段新增/更新一个章节 |
| 约束与入口 | `AGENTS.md`、`README.md` | 工程红线、当前阶段指针、快速上手 | 每阶段开始/发布时更新 |

> 原则：**阶段规划在 ROADMAP，技术细节在技术文档，历史在冻结层。** 同一个事实只写一处；需要引用时给链接，不复制。技术文档中的下一阶段增量先标"未实现"，交付后改为实装说明。

### 0.2 阶段生命周期

```text
Backlog ──► Planned ──► In Progress ──► Delivered ──► Closed
 想法       已确认范围      开发中           验收通过        阶段记录归档
```

- 状态只能前进（可回退到 In Progress 修复问题）；状态变化更新 §2 索引表与对应章节头部。
- 一个阶段内允许拆分 M0/M1/M2 里程碑，但不拆出新文档。
- 阶段 `Closed` 后，章节保留为记录；详细规格可压缩为摘要 + 指向技术文档"实装补充"。

### 0.3 每阶段要写的文档（固定动作）

| 时机 | 动作 |
|---|---|
| 有新想法 | 写入 §6 Backlog（含触发条件），不直接开工 |
| 确认要做 | 在 §4/后续章节按模板写规格（状态 Planned），更新 §2 索引 |
| 开工 | 状态 In Progress；更新 `AGENTS.md` 的"当前阶段"；必要时更新 `README.md` 状态 |
| 开发中 | 每周更新本章"交付记录"；技术决策变更写本章"决策记录" |
| 交付/验收 | 技术增量追加到 `ARCHITECTURE.md`/`DATA_MODEL.md`/`UI_GUIDE.md` 的"Phase N 实装补充"；写 §7 发布记录；状态 Delivered |
| 关闭 | 按 §8.3 清单检查；状态 Closed；Backlog 中相关条目标记完成 |

### 0.4 阶段与版本号

- Phase 与版本一一对应：Phase 5 → `v0.3.0`，Phase 6 → `v0.4.0`，以此类推。
- MVP 版本保留 `-mvp` 后缀（`v0.1.0-mvp`、`v0.2.0-mvp`）；post-MVP 不再使用该后缀。
- **文档版本：** 所有 living 文档（本文件、`ARCHITECTURE`、`DATA_MODEL`、`UI_GUIDE`）的“文档版本”= 最近一次交付的阶段版本。当前为 `v0.2.0-mvp`；Phase 5 交付时统一升到 `v0.3.0`，不为每次编辑单独升版本。
- tag 由用户在阶段验收后创建；Agent 不执行 Git 写操作。

---

## 1. 北极星与不变量

### 1.1 一句话

mousehole 是**面向个人用户的 Local-first AI Workspace**：把资料、任务、执行过程和成果沉淀在同一个持续存在的工作空间里，让工作空间**越用越值钱**。

### 1.2 三个不变量（任何阶段都不能破坏）

1. **成果独立且可追溯**：Artifact 不依附于聊天记录，版本不覆盖历史，来源可追溯。
2. **上下文显式且受预算约束**：可用上下文 ≠ 实际输入；不把全文无预算地拼进 Prompt。
3. **工具受控**：模型只能调用 allowlist 内的工具，无 Shell、无任意文件系统、无未经确认的外部写。

### 1.3 新功能的三问

- 是否强化"资料 → 任务 → 执行 → 成果 → 复用"的闭环？
- 是否让结果更可核对、更可复现？
- 是否仍然符合单用户、local-first、桌面优先？

三问都答不上来的功能，进 §6 Backlog，不进当前阶段。

### 1.4 成功观

- 先 dogfooding：自己的真实项目连续使用 4 周，比功能数量更能说明问题。
- 每个阶段都要有**可演示**的验收场景，不靠"已完成"口头声明。
- 指标示例：成果复用率、历史成果找回成本、失败可定位率、升级零丢失。

---

## 2. 阶段索引

| Phase | 版本 | 主题 | 状态 | 周期 | 验收基线 |
|---|---|---|---|---|---|
| 1–4 | `v0.2.0-mvp` | MVP：核心闭环与可用性 | Closed | 2026-11 前 | `archive/mvp/MVP_SPEC.md` §8 |
| **5** | **`v0.3.0`** | **复用与可信** | **In Progress** | 2026-11-23 起，约 6 周 | 本文 §4.8 |
| 6 | `v0.4.0` | 输入与规模（候选） | Backlog | 待定 | 触发条件见 §5.1 |
| 7 | `v0.5.0` | 集成与自动化（候选） | Backlog | 待定 | §5.2 |
| 8 | `v0.6.0` | 能力体系与评估（候选） | Backlog | 待定 | §5.3 |

> 状态定义：Backlog = 想法/候选；Planned = 范围已确认待开工；In Progress = 开发中；Delivered = 已交付待验收/已验收；Closed = 阶段记录归档。

---

## 3. 已完成：Phase 1–4（MVP，Closed）

- Phase 1：Workspace / Project / Task / File / 文件继承与引用、Alembic、测试基础。
- Phase 2：Conversation、Provider 适配（OpenAI / DeepSeek / Ollama）、流式响应。
- Phase 3：确定性 Execution Pipeline、状态机、Scheduler、快照、Artifact 版本、Skill Library、受控工具、SSE。
- Phase 4：Home 统计、Project Overview、Library 筛选排序、运行历史、Docker 生产/开发栈、备份恢复、Playwright E2E、文件预览、临时文件单轮化。

详细交付记录见 `archive/mvp/DEVELOPMENT_PLAN.md`；验收标准见 `archive/mvp/MVP_SPEC.md` §8。本阶段不再扩展。

---

## 4. 当前阶段：Phase 5 — v0.3.0「复用与可信」

> 状态：In Progress　周期：约 6 周（2026-11-23 起）
> 一句话：MVP 证明了"一次闭环能跑通"，Phase 5 证明"越用越值钱"——让成果能复用、让过程能核对。

### 4.1 背景与诊断

1. **复利断裂（最严重）**：Artifact 只能看/下载/删除，不能编辑，也不能作为新 Task 的输入；前端无全局成果入口；"从成果派生任务"未实现。工作空间只"积累文件"，不"积累能力"。
2. **可信缺口**：成果无引用（citation），无法核对结论来自哪份资料哪一段；看不到模型实际看到了什么（无上下文清单/成本）；无法比较两次运行；Chat 失败只走 SSE、刷新即丢。
3. **日常摩擦**：Task/Project 无服务端搜索（仅 limit）；无 Prompt 模板，成功执行不能沉淀为 Skill；对话不能清空/重开；取消执行有 API 但前端无入口。
4. **工程债**：解析阻塞事件循环、无日志脱敏、SQLite 测试不覆盖 Postgres 迁移、Chat 意图靠中文关键词、前端巨石组件、并发硬编码。

与 Phase 3 的目标关系：Phase 3 让"执行可追溯"；Phase 5 把同一套可追溯能力延伸到"成果复用期"，**不改变**确定性 Pipeline、受控工具、Artifact 独立、无 RAG 的边界。

**方向取舍（为什么不是其他）：**

| 方向 | 判断 | 理由 |
|---|---|---|
| A. 复用与可信（选中） | 本阶段 | 直接放大已有闭环价值；顺架构；可审计、可演示；与"个人研究工作台"定位一致 |
| B. 输入广度（Office/OCR、MCP、GitHub、IDE） | 推迟到 Phase 6/7 | 新依赖 + 安全审批 + 维护成本；容易变成"另一个 AnythingLLM" |
| C. 自动化（定时任务/周报/后台） | Phase 6 候选 | 依赖复用与审阅链路先成立，否则产出一堆没人看的成果 |
| D. 平台化（多 Agent/Workflow 市场） | 不做 | 违背"不是 Agent 平台"的定位；现有确定性 Pipeline 才是优势 |

### 4.2 目标与成功标准

**目标：**

1. **复用闭环**：Artifact 从"终点"变成"下一轮输入"；全局可找；可编辑并保留版本。
2. **可信执行**：每次运行能回答"用了什么模型/参数、看了哪些材料、花了多少、产出什么、错在哪"；两次结果可比较。
3. **日常效率**：全局搜索、服务端搜索/分页、模板/技能沉淀、对话上下文管理。
4. **工程硬化**：先还掉 6 笔会放大后续成本的债。

**成功标准（验收门槛）：**

- 可演示：Project A 的 Artifact 引用进 Project B 的新 Task 并成功执行，来源/版本/快照可追溯。
- 可核对：任一次 Execution 打开运行卡，能看到模型/参数/成本/材料清单/步骤/产出/错误。
- 可找回：任意历史成果 ≤2 次操作可达；Task/Project 列表不再 200 条静默截断。
- 可比较：任意两个 Artifact 版本或两次运行结果可 Diff。
- 可回滚：v0.2.0 真实数据升级 v0.3.0 零丢失（先备份）。

### 4.3 非目标（本阶段明确不做）

RAG / 向量库 / embedding；Office / OCR / 音视频解析；MCP / GitHub / IDE / 外部 Agent；多用户 / 协作 / RBAC / 云同步 / 移动端；多 Agent / 自主规划 / Workflow 可视化 / Skill 市场；多 Conversation；PDF/Office 导出主线；独立搜索引擎。

### 4.4 范围与优先级

| 优先级 | 内容 | 里程碑 | 必交 |
|---|---|---|---|
| P0 | H1–H6 工程硬化 | M0 | 是 |
| P0 | F1 全局 Artifacts、F2 引用成果、F3 编辑/版本/当前、F4 派生 Task | M1 | 是 |
| P0 | F6 运行卡、F7 上下文查看器、F8 Diff、F10 失败留痕/取消/重跑 | M2 | 是 |
| P0 | F11 全局搜索、F12 服务端搜索/分页 | M3 | 是 |
| P1 | F13 模板 / 保存为 Skill、F14 对话上下文管理、H7 前端测试与拆分 | M3 | 是（可裁剪细节） |
| P2 | F5 Project 导出、F9 Citation 试点、H5 配置化 | 时间允许 | 否 |

量级：S ≈ ≤2 天，M ≈ 3–5 天，L ≈ 1–2 周（单人 + AI 辅助粗估）。

### 4.5 功能规格

#### 4.5.1 工程硬化

| 编号 | 事项 | 要点 | 量级 |
|---|---|---|---|
| H1 | 解析移出事件循环 | 读取/解析放入线程池（`asyncio.to_thread`/anyio），线程内不共享 ORM Session；单文件超时（默认 120s）→ 显式 `file_parse_error`。现状：`pipeline.py:202` 在 async 内同步解析 | S–M |
| H2 | 统一日志与脱敏 | `dictConfig`；request_id/task_id/execution_id；过滤 `sk-`、Authorization、Key、文件全文/Prompt；内容日志仅 DEBUG | S |
| H3 | Postgres 集成测试 | `TEST_DATABASE_URL` + `postgres` marker；`alembic upgrade head`；FK/CHECK/UNIQUE/迁移链；无 URL 自动 skip | M |
| H4 | Chat 意图改造 | 输入框"允许工具"开关（默认开）+ 关键词兜底 + `tool_intent_source` 记录；固定测试集 20+20 条 | M |
| H5 | 配置化（P2） | 并发数（现硬编码 2）、默认预算、模型窗口表进配置 | S |
| H6 | 文档漂移记录 | ExecutionStep 已持久化、迁移 head `n4o5p6q7r8s9`、测试数 107、UI Execution 口径；归档文档不修改，以本文与技术文档"实装补充"为准 | S |
| H7 | 前端测试与拆组件（P1） | 引入 vitest（需批准）；抽 `useChatStream`/`useExecutionProgress`；≥15 单测；TaskView 1560 行 / ChatPanel 1299 行下降 | M |

#### 4.5.2 复用闭环

| 编号 | 功能 | 价值 | 要点 | 量级 |
|---|---|---|---|---|
| F1 | 全局 Artifacts 页（`/artifacts`） | 跨 Project/Task 找到所有成果 | 列表/筛选/搜索；独立详情 `/artifacts/:id`；导航新增 Artifacts | M |
| **F2** | **Task 引用 Artifact 作为上下文（旗舰）** | 成果成为下一轮输入，闭环升级 | 新关联表（钉版本）；输入框「+」引用；Budget 参与截断；快照 + manifest 记录；删除被引用成果 409 | L |
| F3 | Artifact 编辑 / 版本 / 当前版本 | 在工具内完成最终交付 | 编辑 = 新增版本（append-only，`source_type=manual`）；`set_current_artifact` 补 API/UI；不原地改 | M |
| F4 | 从 Artifact 派生 Task | 一键"基于这篇报告做下一步" | 预填 Task + 自动引用 + 继承 Project | S |
| F5 | Project 导出（P2） | 可迁移交付/归档 | zip：manifest + Markdown + 可选文件；不导出 Key | M |

#### 4.5.3 可信执行

| 编号 | 功能 | 价值 | 要点 | 量级 |
|---|---|---|---|---|
| F6 | 运行卡 | 一眼看清模型/参数/成本/材料/步骤/产出/错误 | 扩展 `GET /executions/{id}`；成本用可配置价格表，缺失显示"—（不完整）" | M |
| F7 | 上下文查看器 | 展示模型实际看到的材料构成 | `context_manifest`（只存清单/统计，不存全文/Prompt）；Chat 用 Message.metadata | M |
| F8 | 版本/运行 Diff | 迭代与验收可比较 | 前端自写轻量行级 Diff（引依赖需批准）；长文档分块渲染 | M |
| F9 | Citation 试点（P2） | "文档→结论"证据链 | Prompt 约定 `[来源: 文件名 p.N]`；PDF 保留页码（先 spike）；无法定位显式标注；不阻断保存 | L |
| F10 | 失败留痕 + 取消/重跑 | 失败可复现、可重试；长任务能停 | Chat 失败消息持久化 + 重试；前端接 `POST /executions/{id}/cancel`；重跑生成新 Execution | S–M |

#### 4.5.4 日常效率

| 编号 | 功能 | 要点 | 量级 |
|---|---|---|---|
| F11 | ⌘K 全局搜索 | 聚合 Project/Task/File/Artifact/Message；先 ILIKE + 索引，不引外部引擎；1 万行 P95 <300ms | M |
| F12 | 服务端搜索/分页 | Task/Project 加 `search`/`offset`/`has_more`；前端移除固定 200 上限；Library 分页 | M |
| F13 | 模板 / 保存为 Skill（P1） | `prompt_templates` + 内置 3 个 seed；仅预填 Task 描述，不改 Pipeline；运行卡"保存为 Skill" | M |
| F14 | 对话上下文管理（P1） | `conversations.context_reset_at`；清空/从某条重开；历史仍可见；不引入多 Conversation | M |

#### 4.5.5 关键规则（不可含糊）

- **引用钉版本**：新版本不自动扩散；"更新到最新"是显式操作；执行快照记录版本。
- **Artifact 编辑 append-only**：保存创建新版本，旧版本不变；当前版本只移动指针。
- **manifest 不存全文**：只存 kind/id/name/tokens/usage_mode；红线 7。
- **失败不伪装成功**：取消 ≠ 失败；Artifact 保存失败不得标记 Completed。
- **Citation 可降级**：定位失败标注"未定位"，不阻断执行与保存。

### 4.6 技术增量（详见技术文档）

| 层 | 增量 | 落点 |
|---|---|---|
| 数据 | `task_artifacts`（task_id、artifact_id、artifact_version，UNIQUE(task_id, artifact_id)，删除保护 409） | `DATA_MODEL.md` §5.1 |
| 数据 | `execution_artifact_snapshots`（execution_id、artifact_id、version、usage_mode、hash；UNIQUE 三元组） | §5.2 |
| 数据 | `executions.context_manifest` JSONB（budget/model_window/items；不存全文） | §5.3 |
| 数据 | `prompt_templates`（workspace_id、name、content；UNIQUE(workspace_id,name)） | §5.4 |
| 数据 | `conversations.context_reset_at`（DateTime nullable） | §5.5 |
| API | 全局 artifacts、series/current、series/versions、tasks/artifacts、executions detail 扩展、search、tasks/projects search、prompt-templates、context-reset、projects export | 本文件 §4.6.1 |
| 前端 | Artifacts 页/详情、引用成果、运行卡、上下文查看器、Diff、⌘K、模板、对话管理、取消/重跑 | `UI_GUIDE.md` §6 |

> 数据表字段定义、前端交互细节以技术文档为准；本文件只记录"做什么、为什么、怎么验收"。

#### 4.6.1 API 变更清单

| 方法 | 路径 | 说明 | 里程碑 |
|---|---|---|---|
| GET | `/api/v1/artifacts` | 全局成果列表（筛选/搜索/分页） | M1 |
| PATCH | `/api/v1/artifact-series/{id}/current` | 切换当前版本 | M1 |
| POST | `/api/v1/artifact-series/{id}/versions` | 手动编辑新增版本 | M1 |
| GET/POST/DELETE | `/api/v1/tasks/{id}/artifacts` | Task 引用成果 | M1 |
| GET | `/api/v1/executions/{id}`（扩展） | steps/snapshots/artifacts/context_manifest | M2 |
| GET | `/api/v1/search` | 全局搜索 | M3 |
| GET | `/api/v1/tasks`、`/projects`（扩展） | search/offset/has_more | M3 |
| CRUD | `/api/v1/prompt-templates` | 模板管理 | M3 |
| POST | `/api/v1/conversations/{task_id}/context-reset` | 设置/清除上下文重置点 | M3 |
| GET | `/api/v1/projects/{id}/export` | 项目导出 zip | P2 |

### 4.7 里程碑

| 里程碑 | 时间 | 交付 | 验收 |
|---|---|---|---|
| M0 硬化 | 第 1 周 | H1、H2、H3、H4、H6（H5 可选） | 大 PDF 不卡 API；SQLite+Postgres 测试全绿 |
| M1 复用 | 第 2–3 周 | F1、F2、F3、F4 | 跨 Project 引用执行成功，快照/manifest 正确 |
| M2 可信 | 第 3–5 周 | F6、F7、F8、F10 | 运行卡信息完整；取消不产出；Diff 正确 |
| M3 效率 | 第 5–6 周 | F11、F12、F13、F14 | 5 类实体可搜；模板建 Task；清空上下文生效 |
| P2 可选 | 第 7 周 | F5、F9、H5、H7 剩余 | 视时间裁剪，不阻塞发版 |

### 4.8 测试与验收

- **单元**：上下文预算（文件+成果+Skill 混合排序/截断）、钉版本、引用删除保护、版本追加/当前切换、模板、context_reset 过滤。
- **集成（Postgres）**：迁移 upgrade/downgrade、FK/CHECK/UNIQUE、引用与快照一致性、导出 zip。
- **API**：参数校验、409、状态限制、错误格式。
- **E2E**：`phase5-reuse`（引用→执行→快照/manifest）、`phase5-search`（⌘K）、`phase5-run-card`（运行卡/取消/重跑）。
- **回归**：现有 107 pytest + 3 E2E 保持绿。
- **人工验收**：用真实资料完成"跨 Project 复用 → 运行卡核对 → Diff → 编辑成果 → 新建 Task"一条链；截图/输出贴入交付记录。

### 4.9 风险与回滚

| 风险 | 缓解 |
|---|---|
| 范围过大 | P0 必交；P1 可裁剪；P2 时间允许 |
| 数据变更 | 全部增量迁移；升级前备份；Postgres 集成测试；提供 downgrade |
| 上下文被成果挤占 | 显式 budget 规则 + 截断提示 + manifest 可查 |
| 引用版本扩散 | 钉版本 + "更新到最新"显式操作 + 快照记录 |
| Diff/搜索性能 | 前端分块渲染；先 ILIKE/索引，量大再 FTS |
| Citation 模型不遵循 | 降级不阻断；标注"未定位"；P2 |
| 前端回归 | M0 引 vitest；每主题拆组件；E2E 回归 |

### 4.10 开放问题

| # | 问题 | 现状处理 | 需确认时点 |
|---|---|---|---|
| 1 | Workspace 是配置项还是组织层 | 按"配置项"处理；成果按 Project/Task 归属 | M1 前 |
| 2 | Chat 成果与 Execution 成果边界 | 沿用 `source_type`，不合并 | M2 前 |
| 3 | usage 缺失展示口径 | 运行卡显示"—（不完整）" | M2 前 |
| 4 | PDF 页码可定位性 | M0 做解析 spike；不可行则 Citation 降级为文件级引用 | M0 |
| 5 | 模板是否影响 Execution Prompt | 仅预填 Task 描述，不改 Pipeline | M3 前 |

### 4.11 决策记录（已确认 2026-11-23）

- 主题确定为「复用与可信」，不做 RAG/向量库、Office/OCR、MCP、多用户、多 Agent、Workflow 市场。
- 成果引用**钉版本**；被引用成果删除返回 409；快照记录版本与使用方式。
- Artifact 编辑采用 **append-only 新增版本**，不原地修改；补 `set_current_artifact` API/UI。
- 上下文清单以 `context_manifest` JSON 持久化（只存清单与 token，不存全文/Prompt）。
- 对话上下文管理用 `conversations.context_reset_at`，不引入多 Conversation。
- 先做 M0 工程硬化再进入功能开发；每周末更新本文交付记录。

### 4.12 交付记录

| 日期 | 里程碑 | 状态 | 测试 | 备注 |
|---|---|---|---|---|
| 2026-11-23 | 范围与规格确认 | Done | 后端 107 passed（基线） | 本文建立 |
| — | M0 | 待开始 | — | H1 起 |
| — | M1 | 待开始 | — | |
| — | M2 | 待开始 | — | |
| — | M3 | 待开始 | — | |

---

## 5. 后续阶段（Phase 6+，候选，不承诺）

> 只写方向与触发条件；不排期、不写详细规格。触发后按 §8 模板升级为 Planned。

### 5.1 Phase 6 候选：输入与规模

- **Office 解析**（docx/xlsx/pptx）：4 周内 ≥3 次因格式受阻再做；先 docx/xlsx，走依赖审批。
- **检索增强**：真实任务中 >30% 受预算截断影响，或单项目 >20 份资料 / >50MB；先 Postgres 全文/关键词检索 + 引用，再评估 embedding/RAG。
- **定时任务/周报**：在复用与审阅链路稳定后做；需要新的调度实体与 UI。
- **文件版本 / 批量导入导出**：Library 规模化后。

### 5.2 Phase 7 候选：集成与自动化

- **MCP（只读、白名单）**：先有工具审批 UI 与权限模型；仍走 TOOLS_SPEC allowlist。
- **GitHub / 仓库分析**：只读拉取 + 本地归档，不自动写外部。
- **IDE / CLI 接入**：先做"导出上下文/成果"的轻量方式，不做双向同步。
- **外部 Agent**：需要任务边界与权限设计，优先级最低。

### 5.3 Phase 8 候选：能力体系与评估

- **Skill 版本/组合**、**轻量 Workflow 模板**、**Mini Eval**（固定任务集比较模型/参数/Skill）、**成本报表**。
- 均建立在现有 Execution/Artifact/Skill/快照之上，不引入 Agent 平台化。

---

## 6. Backlog（未排期）

| 功能/方向 | 来源 | 价值 | 触发条件/备注 |
|---|---|---|---|
| RAG / 向量检索 / embedding | MVP_SPEC 后续扩展 | 大规模资料检索 | 见 §5.1 检索触发条件；先 Postgres 检索 |
| Office / OCR / 音视频 | MVP_SPEC 非目标 | 输入覆盖 | 4 周 ≥3 次受阻；依赖审批 |
| MCP / GitHub / IDE / 外部 Agent | MVP_SPEC P1 | 外部协作 | 先权限审批模型 |
| 多 Conversation | DEVELOPMENT_PLAN 已知限制 | 长对话组织 | 先用 F14 缓解；真需求再提案 |
| 文件版本控制 | MVP_SPEC P1 | 资料迭代 | 与 File 引用规则一起设计 |
| PDF / 幻灯片导出 | MVP_SPEC P1 | 交付形态 | F3/F5 之后再评估 |
| HITL / 工具审批历史 | PRODUCT_SPEC | 高风险工具前置 | 引入有副作用工具前必须做 |
| 成本报表 / 预算告警 | MVP_SPEC P1 | 费用可控 | 运行卡数据稳定后 |
| Mini Eval / 模型对比 | 学习笔记 §9 | 选型与复盘 | Phase 8 候选 |
| 多 Workspace / 组织层 | 开放问题 | 工作组织 | 先厘清 Workspace 语义 |
| 定时摘要 / 周报 | 提案 C 方向 | 自动化积累 | Phase 6 候选 |
| 移动端 / 云同步 / 协作 | MVP_SPEC 非目标 | — | 不做（与定位冲突） |

> 来源列中的 `MVP_SPEC` / `PRODUCT_SPEC` / `DEVELOPMENT_PLAN` 均指 MVP 期文档，已归档在 `archive/mvp/`，仅作追溯；学习笔记见 `notes/PROJECT_LEARNING_GUIDE.md`。

---

## 7. 发布记录

| 版本 | 主题 | 日期 | 主要变更 |
|---|---|---|---|
| `v0.1.0-mvp` | MVP 初始闭环 | — | Project/Task/File/Execution/Artifact 基础 |
| `v0.2.0-mvp` | MVP 完成 | 2026-11 | 统计/Overview/筛选/Docker/备份/E2E/预览/SSE/临时文件单轮化 |
| `v0.3.0` | Phase 5 复用与可信 | 计划中 | 见 §4 |

---

## 8. 阶段流程与模板

### 8.1 开启新阶段（Checklist）

1. 从 §6 Backlog 选主题，明确**触发条件已满足**。
2. 写"目标 / 非目标 / 范围（P0-P2）/ 验收标准"，放入 §4 之后的新章节（状态 Planned）。
3. 用户确认范围与关键决策（尤其核心实体、新依赖、架构边界）。
4. 更新 §2 索引与 `AGENTS.md` 当前阶段指针；状态 In Progress。
5. 拆里程碑（M0…），每周更新交付记录。

### 8.2 阶段规格模板（复制使用）

```markdown
## Phase N：vX.Y.Z「主题」（状态）

### 1. 背景与诊断
### 2. 目标与非目标
### 3. 范围与优先级（P0/P1/P2）
### 4. 功能规格（编号 + 价值 + 要点 + 量级）
### 5. 技术增量（数据/API/UI；落地后回填技术文档）
### 6. 里程碑与时间
### 7. 测试与验收（可演示场景）
### 8. 风险与回滚
### 9. 开放问题
### 10. 决策记录（已确认）
### 11. 交付记录（日期/里程碑/状态/测试/备注）
```

### 8.3 阶段关闭 Checklist

- [ ] 验收场景可演示，测试输出真实（贴结果）。
- [ ] 数据迁移可升级可回滚；真实数据备份/恢复演练。
- [ ] 技术增量已追加到 `DATA_MODEL.md` / `ARCHITECTURE.md` / `UI_GUIDE.md` 的"实装补充"。
- [ ] §7 发布记录已更新；`README.md` 状态已更新。
- [ ] §6 Backlog 中相关条目已标记完成或改写。
- [ ] 未解决问题/已知风险写入本章；状态 Closed。

### 8.4 文档更新矩阵（速查）

| 文档 | 阶段开始 | 开发中 | 交付时 | 关闭后 |
|---|---|---|---|---|
| `ROADMAP.md` | 新增章节/索引 | 交付记录 | 验收结果 | 摘要保留 |
| `AGENTS.md` | 当前阶段指针 | — | 边界更新 | 保持 |
| `README.md` | 状态 | — | 能力/文档入口 | 保持 |
| `DATA_MODEL.md` | — | — | Phase N 实装补充 | 只读参考 |
| `ARCHITECTURE.md` | 规划可写本文 | — | Phase N 实装补充 | 只读参考 |
| `UI_GUIDE.md` | 规划可写本文 | — | Phase N 实装补充 | 只读参考 |
| `archive/mvp/` | 不修改 | — | 不修改 | 不修改（MVP 记录） |

---

## 9. 命名与归档规则

- **阶段编号**连续：Phase 5、6、7…；**版本**每阶段次版本递增（`v0.3.0`、`v0.4.0`）。
- **不建 Phase 专属文档**；阶段内容只进本文。若某阶段内容超过约 800 行，再讨论是否拆分（拆分后仍在本文件索引）。
- 阶段 Closed 后：技术文档保留"实装补充"；本文保留目标/范围/决策/验收摘要，详细过程可压缩。
- **MVP 冻结层**（`archive/mvp/` 下的 `PRODUCT_SPEC`、`MVP_SPEC`、`TECHNICAL_DECISIONS`、`DEVELOPMENT_PLAN`）不再改动；需要新口径时写入本文或技术文档"实装补充"。
- **living 文档**（`ROADMAP`、`ARCHITECTURE`、`DATA_MODEL`、`UI_GUIDE`）的文档版本跟随最近交付阶段：当前 `v0.2.0-mvp`，Phase 5 交付后升 `v0.3.0`。

---

## 10. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-23 | 建立本文；Phase 5 范围确认并写入（原两个 Phase 5 草稿已合并删除）；文档结构重构：MVP 文档归档至 `archive/mvp/`，技术文档瘦身为 `ARCHITECTURE` / `DATA_MODEL` / `UI_GUIDE`，文档版本统一为 `v0.2.0-mvp` |

---

## 附录 A：Phase 5 立项参考（外部产品，2026-11 检索）

- NotebookLM Studio / 来源锁定：https://9to5google.com/2025/08/06/notebooklm-studio-redesign/
- Claude Projects：https://support.claude.com/de/articles/9517075-was-sind-projekte.md
- ChatGPT Projects：https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- Heptabase AI Action / MCP：https://wiki.heptabase.com/newsletters/2025-12-30
- RAGFlow 0.20 Agentic Workflow：https://ragflow.com.cn/blog/agentic-workflow-whats-inside-ragflow-v0.20.0
- LM Studio 0.3.17（MCP host）：https://lmstudio.ai/changelog/lmstudio/lmstudio-v0.3.17
- Mem 2.0 与关停公告：https://get.mem.ai/blog/introducing-mem-2-0
- Reor 归档分析（本地优先不足以支撑产品）：https://cloud.tencent.cn/developer/article/2686138

**结论：** MVP 之后不需要新的故事，需要把已验证的闭环做深——成果能复用、过程能验证。每个阶段只解决一个核心矛盾；范围外的一切功能都进 Backlog。
