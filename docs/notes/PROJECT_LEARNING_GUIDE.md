# mousehole 项目学习笔记：架构与 Agent 开发

> 这是写给自己看的项目学习笔记，用来自学和复盘。
>
> 目标只有三个：
>
> 1. 搞清楚项目由哪些模块组成、各自负责什么；
> 2. 搞清楚一次 Agent 请求/执行在代码里怎么走；
> 3. 搞清楚如果要自己从零实现，关键步骤对应哪些文件夹。
>
> 完整架构设计见 [ARCHITECTURE.md](../ARCHITECTURE.md)，技术取舍见 [TECHNICAL_DECISIONS.md](../archive/mvp/TECHNICAL_DECISIONS.md)（已归档）。

## 0. 一句话理解

mousehole 是 Local-first 的个人 AI Workspace，不是聊天客户端。它把一次 AI 工作拆成：

```text
Workspace → Project → Task → Execution → Artifact
                 ↘ Conversation
                 ↗ File
```

核心闭环：建 Project → 上传资料 → 建 Task → 组织文件上下文 → 对话/执行 → 保存 Artifact → 重启后继续复用。

关键点：Execution 是一次运行，Conversation 只是聊天记录，Artifact 是独立成果。

## 1. 一分钟架构图

```text
浏览器 Vue 3
  │ REST + SSE
  ▼
Nginx 生产 / Vite 开发
  │ /api 反向代理
  ▼
FastAPI app/api/v1
  │ 只做参数校验与 HTTP/SSE
  ▼
Service 层 app/modules/*/service.py
  │ 业务规则、状态流转、事务
  ▼
Repository + infrastructure
  │ SQLAlchemy、本地存储、模型适配器
  ▼
PostgreSQL + storage/ + data/
```

分层：api → service → repository → infrastructure；模块之间只走公开 Service。

## 2. 目录地图

### 后端 backend/app/

| 目录 | 负责什么 | 关键文件 |
|---|---|---|
| api/v1 | HTTP 端点，保持很薄 | chat.py、tasks.py、files.py、executions.py、artifacts.py、skills.py、task_files.py、stats.py |
| modules/workspace | Workspace 单例与默认配置 | service.py |
| modules/project | Project CRUD、归档、项目文件关联 | service.py、repository.py |
| modules/task | Task CRUD、绑定 Project、删除清理 | service.py |
| modules/file | 上传、哈希、存储、Library、引用、临时文件 | service.py、storage.py、models.py |
| modules/document | PDF/Markdown/TXT/JSON/YAML/CSV/HTML/CSS 文本提取，失败显式抛错 | parsers.py、service.py |
| modules/context | Task 可用文件计算；执行上下文预算/摘要 | service.py、builder.py |
| modules/conversation | 消息、SSE、Chat 上下文、受控工具 | chat_context.py、tools.py、service.py |
| modules/model | Provider 配置、模型解析、流式/非流式调用 | adapters.py、service.py、config.py |
| modules/execution | 状态机、调度器、Pipeline、事件总线 | models.py、scheduler.py、pipeline.py、events.py |
| modules/artifact | ArtifactSeries + 版本、来源、下载 | service.py、models.py |
| modules/skill | 数据库 Skill、seed、Skill 文件、Task 引用 | registry.py、service.py |
| modules/stats | Home 只读统计 | service.py、schemas.py |
| core、shared | 配置、异常、枚举、usage、默认值 | config.py、exceptions.py、enums.py |
| infrastructure | SQLAlchemy Base/Session | database/ |

### 前端 frontend/src/

| 目录 | 负责什么 | 关键文件 |
|---|---|---|
| views | 页面：Home、Projects、ProjectDetail、Task、Library、Skills、Settings | TaskView.vue、HomeView.vue |
| components | Chat、运行进度、成果、文件预览、统计图 | ChatPanel.vue、RunProgress.vue、TaskArtifacts.vue、FilePreviewModal.vue、StatsBarChart.vue |
| api | HTTP 封装、SSE 解析、类型 | client.ts、endpoints.ts、chat.ts、types.ts |
| router、stores | 路由与跨页状态 | index.ts、app.ts |
| utils | 错误、格式化、Markdown | errors.ts、format.ts、markdown.ts |
| e2e | Playwright 核心闭环 | core-flow.spec.ts、mockApi.ts |

### 其他

| 目录 | 内容 |
|---|---|
| backend/tests | 107 个 pytest |
| docs | 产品、数据、架构、UI、决策、计划 |
| scripts | backup.ps1、restore.ps1 |
| storage、data、backups | 文件、Provider 配置、备份 |
| docker-compose.yml / dev | 生产/开发 Docker |

## 3. 两个关键流程

### 3.1 Chat

1. ChatPanel 收集输入、Skill、临时文件，调用 POST /tasks/{id}/messages；
2. chat.py 校验 Task、解析模型、加载历史、构建文件上下文；
3. 工具意图消息先走非流式工具 pre-pass；
4. 模型可调用 read_task_files、read_task_file、save_artifact、create_execution；
5. 工具经 conversation/tools.py 的 allowlist 执行，结果回填；
6. 最终回答统一用 stream_chat 产生 SSE delta；
7. 持久化消息、usage、工具元数据，前端逐段渲染。

关键点：工具不是让模型直接跑代码，而是让模型申请受控函数。

### 3.2 Execution

1. 创建 Execution(pending)；
2. Scheduler 放入 FIFO 队列，默认 2 并发；
3. Pipeline 执行：resolve_files → parse_documents → build_context → model_call → generate_artifact → save_artifact；
4. 每步写 ExecutionStep，通过 SSE 推送 step 事件；
5. ExecutionFileSnapshot 记录实际参与文件及 direct/summarized；
6. 成功写 Artifact，失败写 error_code/message，取消与失败严格区分；
7. 启动时恢复 pending，把僵死 running 标记失败。

关键点：确定性工作流，不是自主规划 Agent。

## 4. Agent 知识地图

| Agent 知识 | 项目中的落实 | 代码 | 测试/证据 |
|---|---|---|---|
| 工具调用 | 4 个受控工具、OpenAI 兼容 schema、allowlist | conversation/tools.py、chat.py | test_chat_tools.py、test_tools_spec.py |
| Agent 循环 | 工具 pre-pass 最多 4 轮，结果回填，最终流式 | chat.py event_stream | test_chat_api.py |
| 上下文工程 | 文件继承/排除、Chat 预算、Execution 预算、摘要 | context/service.py、builder.py、chat_context.py | test_context_rules.py、test_context_builder.py |
| 状态机 | pending/running/completed/failed/cancelled | execution/models.py、service.py | test_execution_service.py |
| 调度并发 | 进程内 FIFO、默认 2 并发、启动恢复 | execution/scheduler.py | test_scheduler.py |
| 长任务执行 | 确定性 Pipeline、步骤、SSE | execution/pipeline.py、events.py | test_pipeline.py、test_execution_api.py |
| 记忆/技能 | 数据库 Skill、seed、Skill 文件、执行快照 | skill/registry.py、service.py | test_skills_api.py |
| 成果溯源 | ArtifactSeries 版本、来源 execution/chat | artifact/service.py | test_artifact_service.py |
| 流式交互 | SSE thinking/tool_call/tool_result/delta/done/error | chat.py、chat.ts、ChatPanel.vue | test_chat_api.py、E2E |
| 失败处理 | 统一异常、失败步骤、错误码，不伪装成功 | shared/exceptions.py、execution/service.py | 多个 pytest |
| 安全边界 | 只操作当前 Task，无 Shell/任意文件系统 | tools.py、providers.py | test_provider_config.py |
| 评估验收 | 107 pytest、Playwright E2E、备份恢复 | backend/tests、frontend/e2e、scripts | 可现场运行 |

### 4.1 Agent 开发关键步骤 → 对应文件夹

如果重新实现一遍，建议按这个顺序读/写代码，而不是从页面组件开始：

| 步骤 | 你要解决的问题 | 本项目对应位置 | 你学到的开发知识 |
|---|---|---|---|
| 1. 定义领域实体 | Task/Execution/Artifact/File 的边界与状态 | backend/app/modules/*/models.py、shared/enums.py | 数据建模、状态枚举、外键与删除规则 |
| 2. 文件与上下文 | 文件如何进入 Task，如何预算、截断、继承 | modules/file、modules/document、modules/context、conversation/chat_context.py | 上下文工程、文件生命周期、预算控制 |
| 3. 模型接入 | 统一 OpenAI/DeepSeek/Ollama 的 stream/complete | modules/model/adapters.py、service.py | Provider 抽象、流式解析、错误归一化 |
| 4. 工具定义 | 模型能调用什么、参数是什么、如何校验 | conversation/tools.py 的 TOOL_SPECS/_wrap | function calling schema、allowlist、最小权限 |
| 5. Agent loop | 模型申请工具 → 执行 → 回填 → 下一轮 | api/v1/chat.py 的 event_stream | 有界循环、工具结果回填、失败回退 |
| 6. 正式执行 | 长任务的状态机、调度、Pipeline、取消 | modules/execution 的 scheduler/pipeline/service/events | 状态机、FIFO 调度、可取消长任务、事件驱动 |
| 7. 流式 UI | SSE 事件如何变成增量消息和进度 | frontend/src/api/chat.ts、components/ChatPanel.vue、RunProgress.vue | SSE 解析、乐观 UI、增量渲染 |
| 8. 成果与溯源 | 结果如何版本化、关联来源、下载 | modules/artifact、modules/skill | 版本模型、provenance、快照 |
| 9. 可靠性与评估 | 如何证明它真的能工作 | backend/tests、frontend/e2e、scripts/backup.ps1 | 单元/集成/E2E、失败显式、备份恢复 |

**阅读建议**：先读第 1–2 步理解数据与上下文，再读第 4–5 步理解 Agent 调用，最后读第 6 步理解执行系统。

### 最值得讲的三点

1. 工具调用是受控函数，不是自由代码执行；
2. 上下文不是全塞进去，而是继承/排除/预算/摘要/快照；
3. 执行结果可追溯：参数快照、文件快照、Artifact 来源、失败显式。

## 5. 关键设计决策

| 决策 | 选择 | 为什么不选另一种 |
|---|---|---|
| 架构 | 模块化单体 + 分层 | MVP 不需要微服务，单进程易调试 |
| 执行 | 确定性 Pipeline | 自主 Agent 不可控、难复现 |
| 检索 | 不引入 RAG/向量库 | 预算 + 继承 + 摘要足够，避免隐藏检索 |
| 工具 | 原生 function calling + allowlist | 文本解析不可靠，allowlist 保安全 |
| 对话/执行 | 分离，Execution 内部化 | Conversation 不承载执行日志/成果 |
| 成果 | ArtifactSeries + 版本递增 | 覆盖旧版本会丢历史 |
| Skill | 数据库化 + 执行快照 | 写死 Prompt 无法复用/追溯 |
| 调度 | 进程内 FIFO，2 并发 | MVP 不需要外部队列 |
| 用户 | 不做登录/多用户 | 个人本地工具 |
| 部署 | 生产 Nginx+FastAPI+PG；开发 Vite+reload | 生产可验收，开发热更新 |
| Chat 临时文件 | 仅当前一轮 | 避免污染 Task 与 Library |
| Chat 文件预算 | 全文优先，64k 上限 | 普通文章读完整，极端多文件再截断 |
| E2E | Playwright Mock API | 不产生模型费用，可重复 |

### 你明确确认过的决策

- 首页统计：轮数=用户消息条数；Token=Assistant Message usage + Execution usage，不重复计数；
- 不做用户系统/显示名，问候语通用；
- Task 与 Conversation 1:1，不做清空/新建对话；
- Chat 内默认折叠历史运行，不展示 Execution ID；
- 备份恢复覆盖 PostgreSQL + storage，不备份明文 Provider Key；
- Docker 生产/开发双模式；
- Playwright E2E 只覆盖一条核心闭环；
- Project Overview + 最近活动；Library 文件名搜索/类型筛选/排序；
- Home 7 天柱状图；不向用户展示 usage 不完整提示；
- Chat 临时文件只停留在发送的那一轮；
- Project/Task 内可直接预览文件内容；
- 最终回答统一 SSE 流式；
- Chat 文件预算提升到 64k；
- README 精简为快速上手。

其他实现细节（分层、状态机、快照、预算算法等）属于技术决策，记录在 docs/。

## 6. 自我检查：我是否真的理解了

不要背功能，尝试不看代码回答：

1. 一次 Chat 请求从用户输入到 SSE delta，中间经过哪些文件/函数？
2. 模型能调用哪些工具？工具执行前由谁校验边界？
3. 文件如何从 Library 进入 Task？哪些规则决定它对 Task 可见/不可见？
4. Execution 和 Conversation 的区别是什么？为什么成果不放在聊天里？
5. 上下文超预算时怎么处理？文件快照记录了什么？
6. 失败和取消分别怎么表示？为什么不能伪装成功？
7. 如果换一个模型 Provider，需要改哪些地方？
8. 如果要加 RAG，应该插在哪一层？为什么现在没做？

### 反复问自己的问题

- 为什么不用 LangChain/AutoGPT？为了看清 Agent 每个环节；框架会隐藏 loop、工具和上下文；
- Agent 到底在哪里？Chat 的受控工具循环 + Execution 的确定性 Pipeline；不是全自主 Agent；
- 上下文怎么控制？文件继承/排除 → 预算 → 截断/分批摘要 → 快照；
- 怎么防工具乱执行？allowlist + Task 边界 + 无 Shell/任意文件系统；
- 怎么保证可信？参数快照、文件快照、Artifact 来源、失败显式、测试；模型本身仍可能出错；
- 这个项目真正的技术积累是什么？可观察、可追溯、可复现的工程约束，而不是功能数量。

## 7. 推荐阅读顺序

### 1 小时理解项目

1. 本文第 0–3 节；
2. conversation/tools.py：工具如何定义/执行；
3. api/v1/chat.py：Agent loop + SSE；
4. execution/pipeline.py：确定性执行；
5. context/builder.py：预算与摘要；
6. artifact/service.py：版本与来源。

### 1 天深入复习

1. 跑一遍真实闭环，记录自己观察到的现象；
2. 对照 backend/tests 找到每个流程对应的测试；
3. 选一个失败/取消案例，走一遍代码路径；
4. 用第 6 节自测，把答不上来的地方记下来；
5. 用自己的话写一页总结：哪些设计是我真的理解了，哪些还只是会用。

## 8. 边界与限制（对自己诚实）

- 没有多用户/权限/协作；
- 没有 RAG/向量检索，上下文是显式预算 + 摘要；
- 没有自主规划 Agent，只有受控工具循环 + 确定性 Pipeline；
- 模型输出不保证完全可复现，但输入、参数、快照、来源可追溯；
- Chat 文件总量超过预算仍会截断，需要 read_task_file 分页；
- E2E 使用系统 Edge，未下载 Chromium；
- UI 已完成 MVP 收尾（All Tasks / Task 左树 / Projects Ledger / 状态色 / 字体统一），后续只做非阻塞优化。

## 9. 未来可发展（现在不做）

- Run Card + Replay/Diff：把一次 Execution 变成可比较的实验记录；
- 上下文查看器：展示模型实际看到的材料与 token 分配；
- Mini Eval：固定任务集比较模型/参数/Skill；
- Skill 演化：从成功执行沉淀可复用 Skill；
- 检索增强：在显式上下文之外增加可解释检索层。

这些方向都建立在现有 Execution/Artifact/Skill/快照之上，不需要推翻架构。
