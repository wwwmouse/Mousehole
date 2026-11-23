# DEVELOPMENT_PLAN.md

> mousehole 开发计划与交付规范

**版本：** v0.1 
**定位：** 定义 mousehole MVP 的开发阶段、交付标准、测试策略和 AI Coding Agent 协作方式 
**关联文档：** PRODUCT_SPEC.md、MVP_SPEC.md、DATA_MODEL.md、TECHNICAL_DECISIONS.md、ARCHITECTURE.md 、UI_SPEC.md 

---

## 1. 开发目标

本计划指导 mousehole MVP 从设计文档进入实际工程实现。

开发采用模块化、分阶段、可验收的方式，最终交付一个能够在本地运行、具有持久化能力，并可以完成多文档技术资料分析的 AI Workspace。

核心目标不是单纯完成所有模块，而是验证完整业务闭环：

**创建 Project → 上传资料 → 创建 Task → 组织上下文 → AI 分析 → 生成 Artifact → 持久化保存 → 再次访问和使用成果。**

## 2. 开发策略

### 2.1 总体策略

采用混合开发方式：

- 首先建立工程骨架、公共基础设施和核心模块边界。
- 随后围绕完整业务闭环推进开发。
- 每个阶段都应产生可运行、可测试、可交付的结果。
- 避免长期只开发后端或前端，导致系统无法端到端验证。

开发顺序应遵循模块依赖关系，但不要求每个模块完全独立完成后才能进入下一模块。

### 2.2 开发环境

采用混合开发环境：

- PostgreSQL 等基础设施通过 Docker Compose 启动。
- 前端 Vue/Vite 在本地开发服务器运行。
- 后端 FastAPI 在本地运行。
- 最终通过完整 Docker Compose 验证部署和持久化。

开发过程中应保证本地开发方式与最终部署方式的配置一致性，避免出现仅在某一种运行方式下才能工作的情况。

### 2.3 开发阶段

MVP 开发压缩为四个 Phase。

#### Phase 1：工程基础与核心数据管理

**目标：建立可以持续开发的工程基础，并实现 Workspace、Project、Task 和文件资料管理。**

主要工作：

1. 初始化 Monorepo 工程结构。
2. 建立 Vue 3 + TypeScript + Vite 前端工程。
3. 建立 FastAPI 后端工程。
4. 配置 PostgreSQL、Docker Compose 和数据持久化。
5. 建立数据库模型、迁移机制和 Repository 基础。
6. 实现基础 API 和前后端通信。
7. 实现 Workspace、Project、Task 的基础管理。
8. 实现 Global Library 文件上传、列表和基本管理。
9. 实现 PDF、Markdown、TXT 文件的基础解析能力。
10. 实现 ProjectFile、TaskFileOverride 相关上下文关联规则。

**阶段交付物：**

- 可以正常启动的前后端工程。
- 可持久化的数据库。
- 可以创建和管理 Project、Task。
- 可以上传、查看和管理文件。
- Project Task 能正确继承项目文件，并支持额外引用和排除。
- 基础自动化测试。

#### Phase 2：Conversation 与模型接入

**目标：实现 Task 内的 AI 对话能力，并建立统一的模型调用接口。**

主要工作：

1. 实现 Conversation 和 Message 管理。
2. 实现 Task 内的对话界面。
3. 实现模型 Provider 配置与密钥管理（设置页可编辑，默认掩码显示）。
4. 实现 OpenAI、DeepSeek、Ollama Provider Adapter。
5. 实现统一 Model Service。
6. 实现流式模型响应。
7. 实现 Task 创建时的模型选择。
8. 实现 Task 创建后的模型切换。
9. 记录模型调用所需的基础信息和 Token usage（Provider 提供时）。
10. 实现必要的错误反馈。

**阶段交付物：**

- 用户能够在 Task 内与 AI 持续对话。
- 至少一个真实云端 Provider 可以正常工作。
- 模型调用接口具有统一抽象。
- 支持流式响应。
- 能够正确记录 Conversation 和 Message。
- 模型调用失败时能够向用户反馈错误。
- 核心自动化测试通过。

#### Phase 3：Execution 与 Artifact 核心闭环

**目标：实现 mousehole 最核心的多文档分析能力。**

主要工作：

1. 实现 Execution（含 ExecutionFileSnapshot）；ExecutionStep 为 P1，仅预留表结构。
2. 实现 Execution Scheduler 和并发控制。
3. 实现文件解析、上下文构建和模型调用 Pipeline。
4. 实现可用上下文与实际输入上下文的区分。
5. 实现多文档分批处理及必要的摘要汇总。
6. 实现 Execution 状态持久化。
7. 实现 SSE 执行状态推送。
8. 实现 ArtifactSeries 和 Artifact。
9. 实现 Artifact 版本管理。
10. 实现 Artifact Markdown 内容生成和持久化。
11. 实现 Execution 历史和实际使用文件快照。
12. 实现失败处理、有限重试和必要的一致性保护。

**阶段交付物：**

用户能够：

1. 创建 Project。
2. 上传多份技术资料。
3. 创建关联 Project 的 Task。
4. 调整 Task 可用文件上下文。
5. 发起多文档分析。
6. 查看 Execution 状态、实时阶段进度与结果摘要。
7. 获取 AI 分析结果。
8. 生成并保存 Markdown Artifact。
9. 查看 Artifact 版本及来源 Execution。
10. 在重新打开应用后访问历史 Task、Execution 和 Artifact。

这是 MVP 最重要的阶段，必须重点保障正确性和可追溯性。

**Phase 3 实现决策（已确认）**

- 上下文预算：按模型窗口自动推导（扣除输出与开销预留），未知模型回退 32k；可在 Workspace 覆盖。
- 超预算：两阶段处理（分批 + 每批摘要 + 汇总），保留来源，不做无限递归。
- 执行时**不自动携带**聊天历史，使用 Task 描述、固定结构化 Prompt 与文件上下文。
- Artifact：固定 ArtifactSeries（首次自动命名，可改标题），每次执行生成单份 Markdown 报告，数据库内联存储，预留 storage_key。
- 快照：只记录实际读取、处理并参与结果的源文件，并标注直接使用 / 已摘要。
- 入口与展示：无独立执行面板；Chat 输入框「+」可引用临时文件/Skill，自然语言由模型判断是否调用受控工具；Execution 仅以 Chat 内「工作进度/运行详情」呈现。
- 取消：支持协作式取消（Pending 直接取消，Running 在安全检查点停止）；取消不是失败。
- 重试：仅网络、超时等临时错误自动重试一次。
- 并发：默认 2；Execution 记录模型与参数快照；首页统计留到 Phase 4。
- Context Service 仅做直接检索 + 文本解析 + 分批组织，**不引入 Embedding / 向量库**。
- Execution 历史必须可回答：模型与配置、实际源文件、直接/摘要、关键步骤、产出 Artifact、失败位置。
- 状态边界：Cancelled ≠ Failed；Artifact 保存失败不得标记 Completed。
- 数据模型优先复用已有实体，仅补充无法表达的内容。

**Phase 3.5 交互与能力层调整（已确认）**

- 自然语言为主要入口：Chat 中由模型判断直接回答、保存成果或启动正式 Execution；保留快捷执行入口。
- 受控工具调用：仅暴露 `read_task_files` / `read_task_file` / `save_artifact` / `create_execution`，只能操作当前 Task，无任意文件系统、Shell 或外部写权限；不支持工具调用的模型自动回退为普通流式对话。
- 概念分离：普通对话不创建 Execution；简单成果可直接保存为 Artifact；多文档分析等正式任务仍由 Execution + Scheduler 管理。
- 上下文规则：Execution 不自动携带聊天历史；"按用户明确指令把对话内容作为执行输入"仍待设计实现（当前仅记录 Execution 输入摘要）。
- 统一成果管理：Artifact 增加 `source_type`（execution / chat）与 `source_message_id`，Chat 与 Execution 的成果共用 Artifact / ArtifactSeries 版本体系。
- Skill Library：全局技能库（主界面导航，与 Library 并列），支持增删改查；Task 只能通过输入框「+」引用库中 Skill；Execution 记录 `skill_id/skill_name` 快照。
- 输入框：「+」内收上传临时文件、引用 Skill、管理 Skill Library；模型选择与 Temperature / Max tokens / 上下文预算（粒子滑杆）在发送按钮左侧，默认值 0.7 / 4096 / 32768；Enter 发送、Shift+Enter 换行。
- 未引入 Agent 框架、多 Agent、复杂权限系统或任意文件操作能力。

**Phase 3.6 调整（已确认）**

- Skill 不止文本 Prompt：`skill_files` 支持上传文件或文件夹（保留相对路径），执行时作为 `skill_asset` 纳入上下文与文件快照。
- Execution 产品层级下调：Artifacts 页不再展示 Execution；Execution 仅作为内部工程实体，UI 以 Chat 内「工作进度 / 运行详情」呈现，且不展示 Execution ID。
- Artifact 独立于 Execution：`source_execution_id` 为可选来源；Chat 成果通过 `source_type=chat` + `source_message_id` 追溯；正式多文档分析仍走 Execution + Scheduler + Pipeline。
- 工具调用可见性：工具 pre-pass 期间发送 `thinking` 心跳；Chat 展示可折叠「工作详情」（工具调用、结果、思考耗时），避免"无输出"的卡死观感。
- Chat 文件上下文：普通对话默认把 Task 可用文件**全文**放入上下文（≤2MB，无单文件 8k 字符截断）；文件预算随 Workspace context budget 调整（默认最多 64k tokens），仅当总量超预算时才截断并提示用 `read_task_file` 分页读取。
- 生成计时：Chat 在思考与流式生成期间持续显示秒数，并在模型静默每 2 秒时收到 `thinking` 心跳（pre-pass 与流式两条路径都覆盖）。
- 输入栏附件语义：临时文件加入 Task 可用上下文后，发送消息即清空输入栏 chips，避免"文件没有随消息发出"的误解；需要继续管理时从「+」菜单或 Task Settings 进入。
- 消息级追溯：Message 增加 `metadata`（迁移 k1l2m3n4o5p6）；用户消息记录 Skill 与文件清单（含来源与预算状态），助手消息记录工具步骤与耗时；UI 在每条消息顶部展示默认折叠的「思路链」，替代原先的"上次工作详情"。
- 模型参数面板仅保留属性名、数值与滑杆（不展示说明文字）。

**Phase 3 完成状态（2026-11-20）**

已交付：

- Execution：状态机、Scheduler（并发 2 / FIFO / 启动恢复）、确定性 Pipeline、6 个关键阶段、快照、取消与失败边界。
- 上下文：预算按模型窗口推导 + Workspace 覆盖；超预算两阶段摘要；Skill 资料（文件/文件夹）纳入快照。
- Artifact：系列 + 版本递增、来源 execution / chat、消息级 source_message_id、下载/删除、Markdown 内联。
- Skill Library：全局技能库（增删改查、文件/文件夹资料）、Execution 记录 Skill 快照。
- Chat：受控工具（read_task_files / read_task_file / save_artifact / create_execution），schema 工厂 _wrap + 动态工具提示；思考心跳与计时；文件/Skill 按消息生效并记录在 Message.metadata；工作进度；默认折叠思路链。
- 大文件：read_task_file 支持 offset/limit 分页；>2MB 不自动展开；上传上限 25MB。
- 模型与参数：输入框内模型控件；显式默认值 0.7 / 4096 / 32768。

验证：

- 后端 97 passed（状态机、快照、Pipeline、Skill、工具、上下文排序、Artifact 下载/删除、消息 metadata 等）。
- 前端 npm run build 通过。
- 真实模型端到端：分析/摘要/保存成果、工具读取文件、大文件分页、错误路径。

已知限制（留待 Phase 4 或后续）：

- 对话历史无法清空；长历史会干扰模型。
- >2MB 文件不能一次性进入上下文，只能分页/下载。
- "按指令把对话内容作为 Execution 输入"未实现。
- 工具调用依赖模型能力，Artifact 兜底仅覆盖明确"保存/导出"意图。
- 无用户自定义 Skill/Workflow，Skill 仅代码/数据库基础字段。

**Phase 4 实现决策（已确认）**

- Home 统计：轮数 = 用户消息条数；Token = Assistant Message usage + Execution usage（互不重复）；缺失 usage 标记不完整。
- 问候语使用通用称呼，不新增 User 实体或 Workspace 显示名称字段。
- 对话历史：暂不支持清空/新建对话，保留 Task 与 Conversation 1:1；通过上下文预算与历史条数控制长对话。
- Execution 历史：Chat 内默认折叠的「历史运行」，用状态/时间/模型表达，不展示 Execution ID；详细步骤按需展开。
- 备份恢复：scripts/backup.ps1 / scripts/restore.ps1，覆盖 PostgreSQL + storage，默认不备份 Provider 凭证；实际验证完整恢复。
- Docker：生产模式 Nginx + Frontend + Backend + PostgreSQL；开发模式 Vite + FastAPI 热更新 + PostgreSQL；数据持久化。
- E2E：Playwright 覆盖一条核心业务闭环（Mock Provider/API）；新增依赖需用户批准。
- Project Overview：轻量概览 + 最近活动；Library 支持文件名搜索、类型筛选、基础排序；不做完整文件引用列表，但删除前检查引用与历史使用。
- 不扩大 MVP 范围；优先核心闭环、交互、Docker 与可靠性。

**Phase 4 实施进度（2026-11-21）**

- 已完成：Home 统计与最近成果、Project Overview、Library 类型筛选/排序、Chat 运行历史、Docker 生产/开发 compose、备份恢复脚本。
- 已验证：生产 compose 构建并启动（frontend 8090 / backend 8000 / postgres 5433），nginx 反代与统计接口正常；backup.ps1 生成 database.sql/storage.tar.gz/manifest.json；restore.ps1 完整恢复后 tasks/messages/artifacts/files 行数与备份前一致。
- 已验证：Playwright E2E 核心闭环通过（Mock API，上传 → Project → Task → 文件预览 → Chat → 成果下载/删除）。
- 本轮追加：Task 临时文件改为**单轮附件**（不进 Library、不写入 Task 上下文）、Project/Task 文件预览、最终回答统一 SSE（工具 pre-pass 仅用于决定/执行工具，完成后重新流式生成）、README 启动说明重写。
- 已验证：开发 compose 运行（5173 Vite / 8000 API / Vite client / API proxy 正常）；切回生产后数据行数不变；生产容器 restart 后服务与数据仍在。
- **Phase 4 完成（2026-11-21）**：MVP 功能验收通过。
- **UI 收尾（2026-11-22）**：All Tasks 全局索引（Global/Project 分组、置顶、三点菜单）、Task 左树快速切换与最近对话时间、Projects Ledger、Task 状态色、字体 token 与 Tab 样式统一；E2E 3 passed，MVP 范围冻结，准备打 tag。

#### Phase 4：完整 UI、系统集成与 MVP 验收

**目标：将核心能力整合成一个可以日常使用的本地 AI Workspace。**

主要工作：

1. 完善 Home Dashboard。
2. 完善 Project 页面。
3. 完善 Task 的 Chat、Settings 和 Artifacts 三个平级页面。
4. 完善 Global Library。
5. 完善 Artifact 查看和版本切换。
6. 完善 Execution 状态、实时阶段进度和错误展示。
7. 完善全局导航、空状态、加载状态和操作反馈。
8. 完善系统配置和异常处理。
9. 执行完整业务闭环测试。
10. 验证 Docker Compose 部署。
11. 验证数据库、文件和 Artifact 持久化。
12. 整理 README、环境配置说明和使用文档。

**阶段交付物：**

- 完整的本地 Web 应用。
- 主要页面和交互符合 UI_SPEC.md。
- 完整业务闭环可以正常运行。
- 核心自动化测试通过。
- Docker Compose 可以正常启动。
- 应用重启后数据仍然存在。
- 达到 MVP 验收标准。

---

## 3. 阶段交付与验收机制

### 3.1 基本原则

每个 Phase 由 AI Coding Agent 自主完成阶段内部的任务拆解、实现、测试和交付整理。

不要求每个模块或每个小任务都经过人工审批。

但每个 Phase 结束后，必须形成完整的阶段交付物，由用户进行人工审查和验收。

### 3.2 Agent 阶段职责

每个阶段开始时，Agent 应：

1. 阅读相关设计文档。
2. 理解本阶段目标和约束。
3. 自主制定内部实施计划。
4. 按照已有架构和技术选型实现功能。
5. 编写并运行必要的自动化测试。
6. 检查已有功能是否受到影响。
7. 整理阶段交付报告。

阶段结束时，Agent 必须提供：

- 本阶段完成的功能。
- 主要代码和模块变更。
- 新增或修改的数据库结构。
- API 和前端功能说明。
- 自动化测试结果。
- 尚未解决的问题。
- 已知限制和潜在风险。
- 建议的人工验收步骤。

### 3.3 人工验收

用户负责阶段最终验收。

验收重点包括：

- 功能是否符合需求。
- 运行结果是否正确。
- 页面交互是否合理。
- 核心业务规则是否被正确实现。
- 测试是否真正覆盖关键场景。
- Agent 是否擅自改变已有设计。

验收不通过时，Agent 根据反馈修复后重新交付。

通过后进入下一阶段。

### 3.4 交付原则

不能仅以 Agent 声称完成作为验收依据。

必须提供实际测试结果和可复现的验证方式。

未完成、存在缺陷或无法验证的功能必须明确标记，不得以完成状态交付。

---

## 4. 测试策略

### 4.1 总体原则

测试资源优先投入核心业务规则和完整业务闭环，不追求为了覆盖率而覆盖所有简单代码。

重点测试：

- 数据关系和约束。
- 文件上下文继承。
- Execution 生命周期。
- 模型调用异常。
- Artifact 保存和版本管理。
- 数据持久化。
- 完整多文档分析流程。

### 4.2 核心测试类型

**Unit Test**

测试关键业务逻辑，例如：

- Project 与 Task 的关系校验。
- 文件继承、额外引用和排除规则。
- 上下文预算与组织逻辑。
- Execution 状态转换。
- ArtifactSeries 版本号生成。
- 文件类型和参数校验。

**Integration Test**

测试关键模块之间的协作，例如：

- 数据库读写。
- 文件存储和解析。
- Model Service 与 Provider Adapter。
- Execution Scheduler 与 Pipeline。
- Artifact 生成和持久化。

**API Test**

测试核心 REST API：

- 正常请求。
- 参数校验。
- 权限和状态限制。
- 异常响应。
- 数据一致性。

**E2E Test**

重点验证完整用户流程：

创建 Project → 上传文件 → 创建 Task → 调整文件上下文 → 选择 Skill / 自然语言发起执行 → 查看工作进度 → 获取 Artifact → 重新访问历史成果。

前端组件测试按实际需要补充，优先保障核心交互。

### 4.3 模型测试策略

模型调用具有费用、网络波动和输出不确定性，因此区分两类测试：

**自动化测试：**
- 使用 Mock Provider。
- 固定输入和预期输出。
- 不依赖真实模型 API。
- 不产生不必要的 Token 费用。

**真实模型测试：**
- 单独进行 Provider 集成验证。
- 使用实际 API 检查请求、流式响应和 usage 信息。
- 真实模型 E2E 作为手动验证项保留（默认 skip，不纳入 CI）；发布前如需可单独执行。

### 4.4 测试失败处理

测试失败时不能直接忽略或绕过。

Agent 应明确说明：

- 哪些测试失败。
- 失败原因。
- 是否影响当前阶段交付。
- 是否存在临时规避方案。
- 是否需要修改既有设计。

---

## 5. AI Coding Agent 协作规范

### 5.1 Agent 的开发权限

Agent 可以在已经确定的架构和技术约束内，自主完成较大范围的模块开发。

允许：

- 自主拆解开发任务。
- 创建和修改模块内部文件。
- 编写业务逻辑和测试。
- 调整模块内部实现。
- 在既定技术栈内选择合理的实现方式。
- 进行必要的重构和错误修复。
- 完成阶段内集成工作。

禁止未经用户确认：

- 修改整体架构。
- 更换既定技术栈。
- 擅自改变核心数据模型。
- 修改产品核心需求和 MVP 范围。
- 引入大型新依赖或新的基础设施。
- 开放原本禁止的高风险操作。
- 以牺牲数据安全或可追溯性换取实现便利。

如果发现现有设计存在问题，应先说明问题、影响和修改建议，等待用户确认。

### 5.2 文档权限

Agent 可以阅读所有项目设计文档。

可以在授权范围内补充实现说明、开发记录和进度信息。

但不得擅自修改以下文档的核心决策：

- PRODUCT_SPEC.md
- MVP_SPEC.md
- DATA_MODEL.md
- TECHNICAL_DECISIONS.md
- ARCHITECTURE.md
- UI_SPEC.md

如果实现过程确实需要改变设计，应先提交变更建议，由用户决定是否修改。

### 5.3 Git 权限

Git 操作由用户控制。

Agent 不得自行：

- 创建或切换分支。
- 执行 git commit。
- 执行 git push。
- 修改远程仓库。
- 擅自重写 Git 历史。

开发过程中 Agent 可以查看 Git 状态和差异，但所有代码变更均保留在工作区。

用户完成阶段审查并验收通过后，自行决定是否提交和推送。

MVP 采用单分支开发，不引入复杂 Git Flow。

---

## 6. 工程管理与质量要求

### 6.1 工程结构

遵循 TECHNICAL_DECISIONS.md 和 ARCHITECTURE.md 确定的 Monorepo 结构。

前后端保持清晰边界，公共配置和文档统一管理。

### 6.2 数据库迁移

所有数据库结构变化必须通过迁移机制管理。

不允许仅通过手动修改数据库结构来完成正式功能开发。

迁移应具备清晰的版本和执行记录。

### 6.3 配置管理

- API Key 等凭证不得硬编码在代码中。
- 提供环境变量或本地配置文件管理机制。
- 提供必要的示例配置文件。
- 不得将真实凭证提交到 Git。
- Docker 和本地开发环境使用一致的配置约定。

### 6.4 日志与错误处理

关键操作必须具有可追踪的日志。

用户可见错误与开发调试日志应适当区分。

敏感凭证和不必要的文件内容不得写入普通日志。

### 6.5 持久化要求

以下内容必须在应用重启后保留：

- Workspace、Project 和 Task。
- Conversation 和 Message。
- Execution 状态与结果记录（ExecutionStep 为 P1）。
- File 元数据及原始文件。
- Execution 文件快照。
- ArtifactSeries 和 Artifact。

不能仅依赖进程内存保存核心业务状态。

---

## 7. MVP 最终验收标准

MVP 以完整业务闭环为核心。

### 7.1 基础运行

- 可以在本地启动 mousehole。
- 可以通过浏览器访问前端。
- 前后端和数据库正常通信。
- Docker Compose 可以启动完整应用。
- 数据库和文件存储具备持久化能力。

### 7.2 工作空间管理

- 可以创建和管理 Project。
- 可以创建 Global Task 和 Project Task。
- Task 能正确关联所属 Project。
- 页面能够查看历史 Project 和 Task。

### 7.3 文件管理

- 支持 PDF、Markdown、TXT。
- 可以上传和管理文件。
- Project 可以引用 Global Library 文件。
- Project Task 默认继承项目文件。
- Task 可以额外引用和排除文件。
- 可用文件与实际使用文件明确区分。

### 7.4 AI 能力

- 可以配置至少一个真实模型 Provider。
- 可以选择和更换 Task 使用的模型。
- Conversation 支持流式响应。
- 可以执行多文档分析。
- 模型调用错误能够正确反馈。

### 7.5 Execution

- 复杂分析任务能够创建 Execution。
- Execution 状态能够持久化。
- 可以查看 Execution 状态与实时阶段进度。
- 可以查看结果摘要与失败阶段；MVP 不要求历史步骤与日志回放。
- 可以记录实际使用的文件快照。
- 失败时能够诚实反馈原因和进度。
- 失败不能伪装为成功。

### 7.6 Artifact

- 可以生成 Markdown Artifact。
- Artifact 独立持久化。
- 可以查看 ArtifactSeries 和版本。
- 可以追溯来源 Execution。
- 新版本不能覆盖历史成果。
- 应用重启后仍可访问成果。

### 7.7 体验与稳定性

- Home、Project、Task、Library 和 Artifact 页面可正常使用。
- Task 内 Chat、Settings 和 Artifacts 三个平级 Tab 的切换正常。
- 关键操作具有明确反馈。
- 页面加载、空状态和错误状态合理。
- 核心自动化测试通过。
- 完整业务闭环通过人工验收。

---

## 8. 开发过程中的范围控制

MVP 开发过程中，应严格控制新增需求。

遇到未预见需求时，按以下原则处理：

1. 如果不影响核心业务闭环，优先放入未来版本。
2. 如果影响数据正确性或安全性，必须解决。
3. 如果现有架构无法支持，应先提交设计变更建议。
4. 不因局部实现困难而擅自改变整体产品方向。
5. 不为技术潮流引入不必要的框架、依赖或基础设施。

MVP 完成后，再根据实际使用反馈规划下一阶段。

---

## 9. 后续演进方向

MVP 完成后，可能的扩展方向包括：

- RAG 与混合检索。
- Agent 执行模式。
- Skill、Workflow、MCP 能力体系。
- 外部 Agent 和 IDE 集成。
- GitHub 和代码仓库分析。
- 更完善的 Artifact 编辑与版本管理。
- 本地模型和更灵活的模型路由。
- 更丰富的 Dashboard 统计。
- 更完善的文件版本管理和执行重放。

这些方向不构成 MVP 的交付要求。

---

## 10. 文档关系

本文件定义开发阶段的组织方式、阶段交付要求和质量标准。

具体开发行为必须遵循：

- PRODUCT_SPEC.md：产品定位与长期方向。
- MVP_SPEC.md：当前版本的功能范围。
- DATA_MODEL.md：核心实体与数据关系。
- TECHNICAL_DECISIONS.md：技术选型和工程约束。
- ARCHITECTURE.md：系统架构和模块职责。
- UI_SPEC.md：界面结构与交互要求。

当开发实现与设计文档发生冲突时，应先识别冲突并提交修改建议，不得默认以代码实现反向覆盖设计决策。
