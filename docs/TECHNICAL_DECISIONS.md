# Technical Decisions

**项目名称：** mousehole  
**文档版本：** v0.1  
**文档定位：** 项目技术决策记录，明确 MVP 的技术选型、架构约束与技术边界。  
**关联文档：** `PRODUCT_SPEC.md`、`MVP_SPEC.md`、`DATA_MODEL.md`

---

## 1. 文档目的

本文档记录 mousehole 的主要技术决策，明确项目采用的技术栈、运行方式、数据存储策略、模型接入方案、执行机制及工程开发规范。

本文档主要回答：

- MVP 使用什么技术构建？
- 为什么选择这些技术？
- 不同模块之间遵循什么技术约束？
- 哪些能力属于 MVP，哪些留待未来扩展？
- AI Coding Agent 在开发过程中可以自主决定什么，不能擅自改变什么？

本文档不负责详细描述每个模块的内部实现。具体模块职责、调用关系和系统架构将在 `ARCHITECTURE.md` 中进一步定义。

## 2. 总体技术原则

mousehole 的技术设计遵循以下原则：

### 2.1 Local-first

应用优先运行在用户自己的设备上，用户资料、数据库及生成成果默认保存在本地。

调用云端模型时，必须明确数据传输边界，不应将用户全部资料无差别发送给外部服务。

### 2.2 简单优先

优先使用成熟、轻量、易维护的技术方案。

不为了技术先进性引入不必要的基础设施，例如：

- 不在 MVP 引入微服务架构。
- 不默认使用复杂任务队列。
- 不为了多 Agent 而设计多 Agent。
- 不在没有实际检索需求时提前实现完整 RAG。

### 2.3 模块化与可扩展

模块应具有明确职责和接口，避免将模型调用、文件处理、任务执行、数据存储等逻辑耦合在一起。

未来可以在不推翻现有基础架构的情况下扩展模型供应商、检索方式、执行能力和成果类型。

### 2.4 可追溯性

Task、Execution、Artifact 之间的关系必须能够被追踪。

模型调用、执行状态、实际使用的文件及成果来源应保留必要记录，保证历史工作的可解释性。

### 2.5 安全边界优先

权限限制必须由程序执行层保障，不能仅依赖 Prompt 要求模型遵守。

MVP 不开放任意 Shell 执行、未经授权的文件覆盖或外部写操作。

---

## 3. 运行形态与部署

### 3.1 运行形态

采用本地 Web 应用（Local Web Application）。

用户通过浏览器访问本机地址使用 mousehole，前端、后端、数据库和文件存储均运行在用户本机环境中。

基本结构：

```text
User Browser
     |
     v
Frontend (Vue 3)
     |
     v
Backend (FastAPI)
     |
     +---- PostgreSQL
     |
     +---- Local File Storage
     |
     +---- Model Providers
```

应用不要求部署在远程云服务器上，也不要求用户购买域名或配置公网服务。

### 3.2 操作系统支持

MVP 以 Windows 为主要开发、运行和测试环境。

技术实现应尽量保持跨平台：

- 使用跨平台路径处理库。
- 避免直接依赖 Windows 专有 API。
- 避免在业务代码中写死操作系统路径。
- 对文件权限、进程管理等存在平台差异的部分进行封装。

未来可以扩展 Linux 和 macOS 支持，但 MVP 不要求完成所有平台的兼容性测试。

### 3.3 Docker 部署

采用 Docker Compose 作为 MVP 主要运行与部署方式。

主要服务包括：

| 服务 | 职责 |
|---|---|
| frontend | 提供 Web 用户界面 |
| backend | 提供 API 和业务逻辑 |
| postgres | 结构化数据存储 |

文件存储通过持久化目录挂载提供，不要求独立部署为一个服务。

开发和正式运行均使用 Docker Compose，但可以通过不同配置文件或环境变量区分开发模式与部署模式。

开发模式支持代码挂载和热更新；部署模式使用构建完成的正式镜像。

### 3.4 数据持久化

必须区分容器生命周期与用户数据生命周期。

以下数据必须持久化：

- PostgreSQL 数据库文件。
- 用户上传的原始文件。
- 生成的 Artifact 文件。
- 必要的应用配置。

容器重建、升级或删除不能直接导致用户数据丢失。

MVP 应提供基本的数据备份与恢复方案，至少能够备份数据库和文件存储目录。

### 3.5 本地服务安全

虽然应用运行在本机，仍然需要考虑服务暴露和访问安全。

MVP 应遵循：

- 默认只允许本机访问 Web 服务。
- PostgreSQL 不直接暴露给外部网络。
- 后端管理接口不应无意间对局域网或公网开放。
- API Key 等敏感配置不得写入普通日志。
- 不将密钥提交到 Git 仓库。

---

## 4. 前端技术栈

### 4.1 技术选型

采用：

| 技术 | 用途 |
|---|---|
| Vue 3 | 前端框架 |
| TypeScript | 类型系统 |
| Vite | 开发服务器与构建工具 |
| Pinia | 全局状态管理 |
| Vue Router | 页面路由 |

### 4.2 选择理由

用户已有 Vue 和 JavaScript 项目经验，继续使用 Vue 可以降低学习和迁移成本。

TypeScript 用于约束前端数据结构，减少前后端字段不一致、状态类型错误等问题。

随着 Workspace、Project、Task、Execution、Artifact 等实体逐步增加，类型系统有助于保持代码结构清晰。

### 4.3 前端约束

- 采用组件化开发。
- 页面组件不直接承担复杂业务逻辑。
- API 请求统一封装。
- 前后端数据结构保持明确。
- 全局状态仅保存确实需要跨页面共享的数据。
- 不将模型调用逻辑直接写入前端。

---

## 5. 后端技术栈

### 5.1 技术选型

采用 Python + FastAPI。

建议配套：

| 技术 | 用途 |
|---|---|
| Python | 后端主要开发语言 |
| FastAPI | HTTP API 框架 |
| Pydantic | 数据校验与结构定义 |
| SQLAlchemy | ORM 与数据库访问 |
| Alembic | 数据库结构迁移 |
| Pytest | 自动化测试 |

### 5.2 选择理由

Python 拥有成熟的 AI、文档处理、数据分析及模型接入生态，适合 mousehole 当前及未来的发展方向。

FastAPI 具有较好的类型支持和接口开发体验，能够满足 MVP 的后端需求。

### 5.3 后端设计约束

- API 层负责请求接收、参数校验和响应。
- 业务逻辑应放在独立服务模块中。
- 数据库访问逻辑应集中管理。
- 模型调用通过统一接口进行。
- 文件存储通过统一存储模块进行。
- 不允许将所有业务逻辑集中在单个 FastAPI 路由文件中。

---

## 6. 数据库与数据访问

### 6.1 数据库选型

采用 PostgreSQL 作为唯一主要关系型数据库。

MVP 不启用 pgvector。

### 6.2 选择理由

mousehole 存在较多实体及其关联关系，例如：

- Workspace 与 Project。
- Project 与 Task。
- Task 与 Conversation。
- Task 与 Execution。
- Execution 与 Artifact。
- Project、Task 与 File。

这些数据具有明确的关系结构，适合使用关系型数据库进行管理。

PostgreSQL 的事务、约束、索引和关联查询能力能够满足当前业务需求，并为未来扩展提供空间。

### 6.3 数据访问

采用 SQLAlchemy 管理数据库访问，Alembic 管理数据库迁移。

数据库结构应以 `DATA_MODEL.md` 为基础。

数据模型变更应通过迁移脚本完成，不允许直接修改生产数据库结构而不留下迁移记录。

数据库落地约定：

- 主键统一使用 UUID v4。
- 枚举字段以 `VARCHAR` + `CHECK` 约束存储，不使用 PostgreSQL 原生 enum。
- 时间统一以 UTC 存储，前端按用户本地时区展示。

### 6.4 未来扩展

未来需要 RAG 时，可以在 PostgreSQL 基础上启用 pgvector。

不因未来可能使用向量检索而提前增加 MVP 的复杂度。

---

## 7. 文件存储

### 7.1 存储策略

采用数据库元数据与本地文件系统分离的方式。

数据库保存：

- File ID。
- 文件名。
- 文件类型。
- MIME Type。
- 文件大小。
- Storage Key。
- Content Hash。
- 创建和更新时间。
- 文件状态。

文件系统保存实际文件内容。

### 7.2 存储模块

文件读写必须经过统一的文件存储模块。

业务逻辑不应直接拼接物理文件路径，也不应依赖某个固定目录结构。

通过 Storage Key 定位文件，使未来更换存储方式时不必大规模修改业务逻辑。

### 7.3 MVP 支持格式

- PDF
- Markdown
- TXT

暂不支持 Word、Excel、PPT、OCR、音视频等格式。

不支持的文件格式应返回明确错误，而不是静默跳过或产生错误分析结果。

### 7.4 文件与数据库一致性

文件写入和数据库记录创建需要考虑失败情况。

例如文件写入成功但数据库记录失败时，应能够清理未被引用的文件或识别异常状态。

文件删除应检查 Project、Task 和历史 Execution 的引用关系：有引用时返回 `409` 与引用列表；无引用时经用户确认后软删除（`status=deleted`）；永不物理删除文件与历史快照。

---

## 8. Artifact 存储

### 8.1 MVP 支持格式

MVP 完整支持 Markdown Artifact。

数据模型保留 Content Type 等字段，为未来增加其他成果类型预留扩展空间。

### 8.2 存储策略

Artifact 元数据存储在 PostgreSQL 中。

小型文本成果可以直接存储内容；需要文件形式保存的成果使用本地文件系统，并通过 Storage Key 定位。

### 8.3 版本管理

遵循 `DATA_MODEL.md` 的设计：

- Artifact 归属于 Task。
- Artifact 通过 ArtifactSeries 组织同类成果。
- 一个 Execution 可以生成零个或多个 Artifact。
- 每次生成新 Artifact 都独立保存，不覆盖历史成果。
- 同一 ArtifactSeries 内版本号递增。
- 一个 Task 可以拥有多个 ArtifactSeries。
- Artifact 记录来源 Execution。
- ArtifactSeries 可以标记当前主要成果。

MVP 不实现版本差异比较、回滚和完整编辑历史。

---

## 9. 模型供应商接入

### 9.1 支持范围

MVP 至少支持以下 Provider：

| Provider | 调用方式 |
|---|---|
| OpenAI | 云端 API |
| DeepSeek | 云端 API |
| Ollama | 本地模型服务 |

架构必须允许未来增加其他模型供应商。

### 9.2 Provider 抽象

后端设计统一的 Model Provider 接口。

不同供应商通过各自适配器实现统一接口，业务逻辑不直接依赖某个供应商的 SDK 或 API 格式。

统一接口至少需要覆盖：

- 模型调用。
- 流式输出。
- 参数传递。
- 错误处理。
- 调用结果解析。

不能假设所有供应商的 API 完全一致。具体适配器应处理各自的接口差异。

### 9.3 Provider 配置

Provider 在全局设置中配置。

用户可以配置多个 Provider，并分别维护必要的连接信息。

MVP 不设置系统默认模型。

未完成配置的 Provider 不应出现在可用模型列表中。

### 9.4 Task 模型选择

用户创建 Task 时选择具体 Provider 和模型。

Task 保存当前模型配置（`model_provider` / `model_name`），创建 Execution 前必须已选择模型。

用户可以在 Task 创建后更换模型，但更换只影响之后新建的 Execution，不修改已经完成的历史 Execution。

每次 Execution 必须记录实际使用的 Provider 和 Model。

### 9.5 模型密钥安全

API Key 等敏感信息不能明文写入普通业务日志，也不能提交到 Git 仓库。

MVP 的密钥管理遵循面向用户的设计：

- 密钥由后端统一管理，保存在本地受限配置文件 `data/provider_config.json`，仅本机可读、不入 Git。
- 用户在 Application Settings 页面配置和修改密钥，不需要编辑任何本地文件。
- 设置页默认掩码显示，用户主动点击后才显示明文；API 响应默认不返回明文密钥。
- `.env` 只作为初始或兜底配置，不是用户日常修改入口。
- 后端读取密钥后仅在调用 Provider 时使用，不得写入日志或错误信息。

已知限制：MVP 的本地配置文件为明文存储（依赖本机文件权限），密钥加密或接入系统凭据管理器留待后续迭代。

### 9.6 数据传输边界

调用云端 Provider 时，只有实际需要的上下文内容才可以发送。

不得默认将整个 Global Library 或 Project 的所有文件发送给模型。

用户需要能够理解云端模型调用与本地 Ollama 调用之间的数据处理差异。

---

## 10. Execution 执行机制

### 10.1 执行模式

采用：

**同步 API 响应 + 异步业务执行。**

两者分别属于不同层次，不构成冲突。

当用户创建 Execution 时：

1. 后端校验请求。
2. 创建 Execution 记录。
3. 将状态设置为 Pending。
4. 提交后台执行。
5. API 返回 Execution ID。
6. 后台执行实际业务流程。
7. 更新 Execution 状态和结果。

基本状态包括：

- Pending
- Running
- Completed
- Failed
- Cancelled

### 10.2 后台执行方案

MVP 使用轻量后台执行机制，不立即引入 Celery、Redis Queue 等复杂任务基础设施。

但执行管理模块必须与具体执行机制解耦，避免未来更换任务队列时影响业务逻辑。

### 10.3 异常与恢复

Execution 状态必须持久化。

应用重启或后台执行进程异常退出时，应能够识别未正常结束的执行记录，并进行合理的异常状态处理。

MVP 不要求实现复杂的断点续跑，但不能将异常中断的 Execution 永久显示为正常运行：启动时发现仍为 Running 的记录，统一置为 Failed，并在 error_message 中标注 interrupted by restart，不新增状态。

### 10.4 执行记录

Execution 应记录：

- 执行序号。
- 所属 Task。
- 实际模型供应商和模型。
- 开始与结束时间。
- 执行状态。
- 输入摘要。
- 错误信息。
- 实际使用的文件快照。
- Provider 返回时的 Token 用量（usage）。
- 生成的 Artifact 及其来源关系。

MVP 不持久化细粒度执行步骤（P1）：运行阶段通过 SSE 推送进度，完成后保存状态与结果摘要；ExecutionStep 表结构预留但不写入细粒度记录。

---

## 11. 前后端通信

### 11.1 通信方式

采用 REST API + Server-Sent Events（SSE）。

### 11.2 REST API

负责普通业务操作，例如：

- Workspace、Project、Task 的创建与查询。
- 文件上传和管理。
- Artifact 查询。
- Execution 创建与状态查询。
- Provider 配置和模型查询。

### 11.3 SSE

负责服务器向前端推送实时信息，例如：

- Execution 状态变化。
- 当前执行步骤。
- 模型流式输出。
- 执行进度和完成通知。

### 11.4 不采用 WebSocket 的原因

MVP 主要需求是服务器向浏览器推送执行状态和生成内容，并不需要复杂的双向实时通信。

SSE 实现成本更低，足以满足当前需求。

未来如果出现实时协作或高频双向交互需求，再评估 WebSocket。

---

## 12. 工程仓库组织

采用 Monorepo，即前后端及项目文档统一存放在一个 Git 仓库中。

建议目录：

```text
mousehole/
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
├── backend/
│   ├── app/
│   ├── tests/
│   ├── alembic/
│   └── requirements.txt
│
├── storage/
│
├── docs/
│   ├── product/
│   │   └── PRODUCT_SPEC.md
│   ├── requirements/
│   │   └── MVP_SPEC.md
│   ├── design/
│   │   ├── DATA_MODEL.md
│   │   ├── TECHNICAL_DECISIONS.md
│   │   ├── ARCHITECTURE.md
│   │   └── UI_SPEC.md
│   └── development/
│       └── DEVELOPMENT_PLAN.md
│
├── docker/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── AGENTS.md
└── README.md
```

实际目录可以在架构设计阶段调整，但应保持前后端、文档、配置和持久化数据的职责清晰。

用户数据目录不应被误提交到 Git 仓库。

---

## 13. 测试策略

采用分层自动化测试，并辅以完整业务流程的手动验收。

### 13.1 后端单元测试

重点测试：

- 文件解析和格式识别。
- 文件上下文继承及排除规则。
- 上下文构建。
- Provider 接口及错误处理。
- Execution 状态转换。
- ArtifactSeries 版本号生成。

### 13.2 API 集成测试

重点测试：

- Workspace 和 Project 创建。
- Task 创建及关联。
- 文件上传和引用。
- Execution 创建与执行状态查询。
- Artifact 保存和版本管理。
- 模型配置与 Task 模型选择。

### 13.3 前端测试

针对关键交互进行适量测试，例如：

- Task 创建。
- 模型选择。
- 文件选择和上传。
- Execution 状态展示。
- Artifact 展示和访问。

不要求对所有 UI 组件进行高覆盖率测试。

### 13.4 端到端验收

至少保证一条完整流程可以正常执行：

```text
创建 Project
    ↓
上传多份技术资料
    ↓
创建 Task
    ↓
选择模型
    ↓
执行文档分析
    ↓
生成 Artifact
    ↓
重新打开并查看历史成果
```

MVP 的验收应以完整业务流程能否稳定工作为核心，而不是单纯追求测试覆盖率数字。

---

## 14. AI Coding Agent 开发规范

AI Coding Agent 是主要编码执行者，但不是项目架构的自主决策者。

### 14.1 授权范围

Agent 可以自主完成较大模块的实现，包括：

- 模块内部代码组织。
- 函数、类及辅助组件设计。
- 模块内部依赖选择。
- 单元测试和必要的集成测试。
- 在既定技术栈内进行实现优化。

### 14.2 必须经过确认的变更

以下事项未经用户确认不得擅自修改：

- 前端或后端核心框架。
- 数据库选型。
- 核心数据模型及实体关系。
- 核心模块职责和依赖关系。
- 项目整体架构。
- 已确认的产品需求和 MVP 范围。
- 引入大型基础设施或改变核心技术路线。

Agent 可以提出变更建议，但不能直接将建议当作已批准的决策。

### 14.3 开发协作流程

```text
确认架构和模块边界
        ↓
分配完整模块开发任务
        ↓
Agent 自主分析与实现
        ↓
Agent 执行测试并提交结果
        ↓
用户审查代码与架构一致性
        ↓
通过后进入下一模块
```

不要求用户审核每一个函数的实现细节，但每个较大模块完成后都必须进行审查。

### 14.4 开发指令

具体开发约束将在 `AGENTS.md` 中进一步定义。

Agent 必须遵守已经批准的产品规格、数据模型、技术决策和架构文档。

---

## 15. MVP 技术边界

### 15.1 MVP 必须实现

- 本地 Web 应用。
- Docker Compose 运行环境。
- Vue 3 + TypeScript 前端。
- Python + FastAPI 后端。
- PostgreSQL 数据库。
- 本地文件存储。
- PDF、Markdown、TXT，以及 JSON / YAML / CSV / HTML / CSS 文本资料处理。
- OpenAI、DeepSeek、Ollama Provider 接入。
- Task 模型选择。
- Application Settings 中的 Provider 配置与密钥管理。
- 同步 API 响应与异步 Execution。
- REST API + SSE。
- Markdown Artifact 保存。
- Execution 和 Artifact 历史记录。
- 核心自动化测试。

### 15.2 MVP 不实现

- 云端 SaaS 部署。
- 多用户及多人协作。
- 微服务架构。
- Kubernetes。
- 复杂任务队列系统。
- ExecutionStep 细粒度步骤持久化与回放（P1）。
- Prompt 模板管理与模板 CRUD（P1）。
- 完整 RAG 和向量检索。
- 多 Agent 协作系统。
- 任意 Shell 执行。
- 完整 Skill、Workflow、MCP 注册管理。
- Artifact 版本差异比较与回滚。
- Word、Excel、PPT 等复杂文件解析。
- WebSocket 实时通信。

### 15.3 未来扩展方向

在现有架构基础上逐步支持：

- Linux、macOS。
- 更多模型供应商和本地模型。
- pgvector 和渐进式 RAG。
- 更成熟的后台任务队列。
- 更多 Artifact 类型。
- Skill、Workflow、Tool、MCP。
- 外部 IDE、GitHub 和其他专业工具。
- 更完整的本地安全、备份与恢复机制。

---

## 16. 技术决策变更原则

本文档作为 MVP 的技术决策基线。

如果开发过程中发现当前决策存在明显问题，可以提出变更，但应遵循：

1. 说明当前方案存在的问题。
2. 给出可选方案。
3. 分析变更成本和收益。
4. 确认是否影响其他模块。
5. 经用户确认后更新相关文档。
6. 保持技术决策与实际代码实现一致。

不应为了局部实现方便而随意破坏整体架构。

---

## 18. Phase 4 实装补充决策

1. **Home 统计口径**：对话轮数 = 用户消息条数；Token = Assistant Message usage + Execution usage；两类记录对应不同模型调用，不重复计数；缺失 usage 标记不完整，不估算。
2. **不引入用户体系**：Home 使用通用问候语，不新增 User 实体或 Workspace.display_name 字段。
3. **对话历史**：MVP 保留 Task ↔ Conversation 1:1，不支持清空/新建对话；上下文预算与历史条数限制长对话。
4. **Execution 历史**：Chat 内以默认折叠「历史运行」呈现，使用状态/时间/Skill 描述，不突出 Execution ID；详细阶段按需展开。
5. **备份恢复**：提供 `scripts/backup.ps1` / `scripts/restore.ps1`（pg_dump + storage 归档）；默认不备份 Provider 凭证；恢复需人工确认。
6. **Docker 交付**：生产模式 = Nginx(frontend) + backend + PostgreSQL；开发模式 = Vite dev + FastAPI --reload + PostgreSQL；数据通过 `storage/`、`data/` 与 pgdata 卷持久化。
7. **E2E**：使用 Playwright 覆盖核心闭环（Mock API/Provider）；新增依赖需用户批准后安装。
8. **Library 范围**：文件名搜索 + 类型筛选 + 基础排序；不做完整文件引用列表，但删除前必须检查引用与历史使用。
9. **不扩大 MVP 范围**：优先核心闭环、交互质量、Docker 交付与可靠性。


---

## 17. Phase 3 实装补充决策

1. **受控工具调用**：工具 schema 由 `_wrap(name, description, properties, required)` 工厂生成；`TOOLS_SPEC` 是唯一 allowlist；系统提示中的工具说明由 `tool_prompt()` 从 TOOLS_SPEC 动态生成，禁止硬编码工具清单。工具只能访问当前 Task 的文件、Artifact 与 Execution，无任意文件系统/Shell/外部写权限。
2. **工具循环**：非流式 pre-pass，最多 4 轮；轮次结束后用**不带 tools 的 completion** 生成最终回答；若返回内容仍含 DSML/工具标记，丢弃并重试一次，仍失败则显式返回错误，不把乱码当正文。
3. **Chat 文件上下文**：默认读取文件全文（≤2MB，取消单文件 8k 字符截断）；文件预算默认最多 64k tokens，并随 Workspace `context_budget_tokens` 自动收紧（预留 6k 给系统/历史/回答）；按 `updated_at` 新→旧排序，提示词要求优先参考最近更新资料；>2MB 文件不自动展开；仅总量超预算时截断并提示用 `read_task_file` 分页读取。
4. **大文件读取**：`read_task_file` 支持 `offset/limit` 分页（每次最多 40000 字符），返回 total_chars/next_offset/has_more；读取上限 25MB，与上传上限一致。
5. **消息追溯**：Message 增加 `metadata` JSON，记录用户消息携带的 Skill/临时文件与助手工具步骤/耗时；不保存完整 Prompt 或文件全文。
6. **Artifact 独立于 Execution**：`source_execution_id` 可空；`source_type` 区分 execution/chat/manual，`source_message_id` 追溯聊天来源；删除单版本不破坏历史，系列为空时删除系列。
7. **Artifact 兜底**：仅当用户明确表达"保存/存为/存成/导出/artifact"且模型未调用 `save_artifact` 时，后端保存最终回答；正常路径仍由模型决定。
8. **默认参数**：Temperature 0.7、Max tokens 4096、上下文预算 32768；Workspace 可覆盖预算，后端与前端使用同一组默认值。
9. **不引入**：Agent 框架、多 Agent、复杂权限系统、向量库、任意文件操作能力。

