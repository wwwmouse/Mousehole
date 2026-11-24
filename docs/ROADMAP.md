# ROADMAP.md — mousehole 演进路线

**文档版本：** v0.3.0  
**状态：** Phase 5 已交付；可信能力后置  
**定位：** MVP 之后的阶段规划文档。一个阶段一个章节，只写清楚三件事：**要解决什么问题、用什么手段、最终结果如何**。技术细节见 `ARCHITECTURE.md`、`DATA_MODEL.md`、`UI_GUIDE.md`。

---

## 1. 北极星

mousehole 是面向个人用户的 **Local-first AI Workspace**：让资料、任务、执行和成果在同一个工作空间里持续积累，**越用越值钱**。

任何阶段都不破坏的三条底线：

1. **成果独立可追溯**：Artifact 不依附聊天，版本不覆盖历史。
2. **上下文显式受预算约束**：可用上下文 ≠ 实际输入。
3. **工具受控**：只允许 allowlist 内工具，无 Shell、无任意文件系统、无未经确认的外部写。

新功能只回答三个问题：是否强化“资料 → 任务 → 执行 → 成果 → 复用”的闭环？是否让结果更可核对、可复现？是否仍符合单用户、local-first、桌面优先？

---

## 2. 阶段总览

| Phase | 版本 | 主题 | 状态 |
|---|---|---|---|
| 1–4 | `v0.2.0-mvp` | MVP：核心闭环与可用性 | 已完成 |
| **5** | **`v0.3.0`** | **复用与效率** | **已完成** |
| 6 | `v0.4.0` | 输入与规模（候选） | 未排期 |
| 7 | `v0.5.0` | 集成与自动化（候选） | 未排期 |

### Phase 1–4 结果

- Phase 1：Workspace / Project / Task / File，文件继承与引用。
- Phase 2：Conversation、Provider 适配（OpenAI/DeepSeek/Ollama）、流式响应。
- Phase 3：确定性 Execution Pipeline、状态机、Scheduler、快照、Artifact 版本、Skill、受控工具、SSE。
- Phase 4：Home 统计、Project Overview、Library 筛选、运行历史、Docker、备份恢复、E2E、文件预览、临时文件单轮化。

结论：**“一次闭环能跑通”已被证明**；Phase 5 开始回答“越用越值钱”。

---

## 3. Phase 5：v0.3.0「复用与效率」

### 3.1 要解决的问题与本阶段处理

| 原问题 | 本阶段处理 | 结果 |
|---|---|---|
| **复利断裂**：Artifact 不能成为新 Task 的输入，成果没有全局入口 | 不建引用表，改为 Artifact 一键导出到 Global Library，复用现有文件继承/引用规则 | 已解决 |
| **过程不可核对**：看不到模型用了哪些材料、参数、成本，运行无法比较 | Execution 不作为产品概念；保留 Artifact 的 `source_*` 追溯字段，运行卡/上下文查看器/Diff 后置 | 有意后置 |
| **日常摩擦**：没有服务端搜索/模板；对话不能清空；长对话 token 压力大 | 先做清空/恢复聊天上下文；内置「流程沉淀」元 Skill；搜索、模板后置 | 部分解决 |
| **工程债**：解析阻塞、日志无脱敏、Postgres 迁移无测试、Chat 工具逻辑脆弱 | M0 工程硬化 H1–H7 | 已解决 |

### 3.2 采用的手段

**复用（M1，已完成）**

- Artifact 一键导出为 Markdown 文件并进入 Global Library（内容寻址；重复导出复用同一 File）。
- 导出后按现有 Library / Project / Task 文件规则复用，不新增 Artifact 引用表，也不改上下文构建管线。
- 导出是快照：之后修改或删除 Artifact 不影响已导出的 File；删除 Task 也不会删除已进入 Library 的文件。
- 全局成果页、成果编辑、派生 Task 等后置；当前只做“成果 → 文件库”这一步。

**效率（M3，本阶段交付子集）**

- Chat 上下文清空/恢复：新增 `conversations.context_start_sequence` 与
  `PATCH /tasks/{id}/messages/context`；消息不删除，只改变下一次请求携带的历史。
- 对话界面增加上下文分界线：线上方明确提示“模型无法读取”，新消息自动落在下方。
- `CHAT_HISTORY_LIMIT` 默认 80 条消息（约 40 轮），可通过环境变量调整。
- 内置「流程沉淀」元 Skill：把一次任务/对话提炼成四段式 Markdown 技能卡，可复制到新建 Skill。
- 跨实体搜索、服务端分页、Prompt 模板、`save_skill` 自动化工具后置。

**工程硬化（M0，已完成）**

- 文件读取/解析移入线程池，可配置超时，超时显式失败。
- 统一日志与 request-id，Key/Token 脱敏。
- Postgres 集成测试（迁移、外键、约束、downgrade）。
- Chat 改为「对话 / 工作」模式：对话无工具；工作模式由模型自行决定是否调用 4 个受控工具；不做关键词猜测，不自动保存成果。
- 并发/超时/预算/模型窗口配置化；前端引入 vitest 并拆分 composable。

**可信（本阶段明确不做）**

- 不展示独立 Execution 页面、运行卡、上下文查看器、版本/运行 Diff、取消/重跑入口。
- 理由：Execution 是内部实现；Artifact 已保留来源字段；这些能力对个人/演示场景收益低，留到真实需要时再提案。

### 3.3 交付范围与后置项

| 状态 | 内容 |
|---|---|
| **已交付** | 工程硬化；Artifact → Library；聊天上下文清空/恢复与分界线；流程沉淀元 Skill；历史条数配置化；项目私有文件上传（交付后补充） |
| **后置** | 全局 Artifacts 页；成果编辑/派生 Task；运行卡/上下文查看器/Diff；⌘K 跨实体搜索；Task/Project 服务端搜索与分页；Prompt 模板；`save_skill` 工具 |

原则：优先“能看见的复用与日常效率”，不引入引用表、不重建上下文管线、不增加新基础设施。

### 3.4 结果与验收

| 里程碑 | 结果 |
|---|---|
| **M0 工程硬化（已完成）** | 大文件解析不阻塞 API/SSE；日志可定位且不泄漏 Key；Postgres 迁移测试通过；工作模式可保存 Markdown 成果；任务删除可级联清理关联数据并返回明确错误。当前测试：SQLite 134 / Postgres 59 / 前端 88 / E2E 3。 |
| **M1 复用（已完成）** | Artifact 可一键「存入 Library」，生成 Markdown 文件；可在 Library 搜索、预览；可被任意 Project/Task 引用；重复导出复用同一文件；删除 Artifact/Task 不影响已导出文件。 |
| **M3 效率子集（已完成）** | Chat 可清空/恢复上下文；清空后旧消息不进入模型，历史不删除；界面有明确分界线；内置流程沉淀元 Skill；历史默认 80 条可配置。 |
| **M2 可信（后置）** | 本阶段不做；保留 Artifact 来源字段作为最小追溯。 |
| **v0.3.0 验收** | 完成“生成成果 → 存入 Library → 新 Project/Task 引用并执行”一条链；清空上下文后模型不再读取旧消息，恢复后重新纳入；迁移可回滚、测试与 E2E 通过。 |

### 3.5 关键规则

- **导出是快照**：Artifact → Library 只复制 Markdown 内容；之后 Artifact 改版本或删除，不影响已导出文件。
- **文件只存一份**：Library 按内容寻址；相同内容重复导出复用同一 File，不产生重复文件。
- **复用走现有规则**：导出的 File 与普通上传文件完全一致，按现有 Project/Task 继承、引用、删除保护规则使用。
- **清空上下文只影响 Chat**：设置 `context_start_sequence`，旧 Message 永不删除；恢复时边界置空，按 `CHAT_HISTORY_LIMIT` 取最近 N 条。
- **历史条数是消息数，不是轮数**：80 条 ≈ 40 轮；完整历史始终可见，只有模型输入被截取。
- **流程沉淀只产出文本**：元 Skill 输出四段式技能卡，不自动写 Skill 库；`save_skill` 工具后置。
- **Chat 模式无工具，工作模式模型决定工具**：不自动保存成果；失败不伪装成功，取消 ≠ 失败。
- **无新基础设施**：不引入引用表、向量库、消息队列、多 Agent、多用户。

### 3.6 非目标与边界

RAG/向量库/embedding；Office/OCR/音视频；MCP/GitHub/IDE/外部 Agent；多用户/协作/云同步/移动端；多 Agent/Workflow/能力市场；多 Conversation；PDF/Office 导出。  
本阶段也不做：Artifact 引用表、上下文构建重构、全局成果页、成果编辑/派生 Task、运行卡、Diff、⌘K、PromptTemplate。  
触发条件（如资料规模、格式受阻频率）满足后再讨论，不在本阶段做。

---

## 4. 后续阶段候选

- **Phase 6 输入与规模**：Office 解析、Postgres 全文检索（必要时再评估 RAG）、定时任务/周报、文件版本。
- **Phase 7 集成与自动化**：只读 MCP、GitHub/仓库分析、IDE/CLI 导出、外部 Agent 接入（先有权限与审批模型）。
- **Phase 8 能力体系**：Skill 版本/组合、轻量 Workflow 模板、Mini Eval、成本报表、`save_skill` 自动化。

均不承诺时间；触发条件满足后按阶段重新写“问题 / 手段 / 结果”三节。
