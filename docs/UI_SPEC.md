# UI_SPEC.md

> mousehole 用户界面设计规格

**版本：** v0.1 
**定位：** 定义 mousehole MVP 的页面结构、布局、交互方式与视觉规范 
**关联文档：** PRODUCT_SPEC.md、MVP_SPEC.md、DATA_MODEL.md、TECHNICAL_DECISIONS.md、ARCHITECTURE.md 

---

## 1. 设计目标

mousehole 的界面应体现现代 AI 工作台的产品定位，同时吸收专业桌面软件的信息组织方式。

界面不应过度强调 AI 的视觉存在感，而应围绕用户的实际工作组织信息，让用户能够自然地创建任务、管理资料、与 AI 协作并查看成果。

### 1.1 核心设计原则

1. **工作空间优先**：以 Workspace、Project、Task、File 和 Artifact 组织界面，而不是简单地围绕 Chat 展开。
2. **对话自然**：Task 内部以 Conversation 为主要交互方式，避免复杂工作流影响日常交流。
3. **信息分层**：常用信息直接呈现，专业信息按需展开，避免界面过度拥挤。
4. **动态反馈**：任务状态、Execution 进度、模型响应等应及时反馈。
5. **操作透明**：明确展示执行状态、实际进度和错误，不允许伪装成功。
6. **成果独立**：Artifact 具有独立的查看入口，不依赖聊天记录才能访问。
7. **上下文可控**：用户能够查看和调整 Task 的文件上下文。
8. **桌面优先**：MVP 面向桌面浏览器，不要求完整移动端适配。

## 2. 整体布局

### 2.1 应用主框架

采用左侧可折叠侧边栏 + 顶部页面信息栏 + 主内容区域。

- 左侧侧边栏：全局导航和主要功能入口。
- 顶部区域：当前页面标题、面包屑、页面级操作。
- 主内容区域：根据当前页面展示工作台、项目、任务或资料。

侧边栏可以折叠，以适应不同桌面屏幕宽度。

### 2.2 全局导航

建议导航结构：

- Home：全局工作台。
- All Tasks：跨 Project 的 Task 全局索引，按 Global Workspace / Project 分组；支持筛选、Project 置顶和三点菜单。
- Projects：项目列表；Project 是可选组织层，不改变 Task 的归属。
- Library：Global Library。
- Skills：全局 Skill Library。
- Settings：应用级设置。

Artifacts 不设独立的全局导航入口：成果按所属 Task 组织，从 Task 的 Artifacts Tab、Project 页面或首页「最近成果」进入。

All Tasks 只是任务视图，不是新的顶层实体；Task 仍属于 Workspace，可选绑定 Project。Task 详情仍可从 All Tasks、首页最近任务、Project 页面进入。

全局导航中的 Home 对应 Global Workspace，不要求用户进入应用后先选择 Workspace 或 Project。

### 2.3 视觉风格

采用现代工作台风格，适当吸收 IDE、专业桌面软件的布局特点。

设计方向：

- 暗色主题作为 MVP 唯一主题。
- 清晰的内容层级和适中的信息密度。
- 适当使用卡片、分区、分隔线和状态标识组织信息。
- 适量使用动态反馈和交互动画。
- 动画服务于状态变化和操作反馈，不追求装饰性效果。
- AI 能力通过实际交互和工作结果体现，不需要大量 AI 装饰元素。

具体颜色、字体、图标、间距和组件样式由前端设计阶段统一确定，不在本规格中锁定。

## 3. 首页：Global Workspace Dashboard

首页是用户进入 mousehole 后的默认页面。

它承担全局工作概览和任务入口的职责，而不是一个默认 Chat 页面。

### 3.1 欢迎区域

页面顶部展示：

- 根据当前本地时间显示问候语：
  - 早上好
  - 中午好
  - 下午好
  - 晚上好
- 用户显示名称。
- 当前日期。

用户显示名称应来自本地用户配置；未设置时使用通用称呼。

### 3.2 使用统计区域

展示近期使用情况，采用柱状图或简洁统计图表：

- 近期 Conversation 轮数。
- 近期 Token 消耗量。

MVP 默认统计最近 7 天的数据，允许后续扩展时间范围。

统计数据应尽量来自实际记录：
- Conversation 轮数依据有效对话消息统计，明确统计口径。
- Token 消耗量优先使用模型 Provider 返回的实际 usage 信息。
- 如果 Provider 未返回 Token 使用量，应明确标记数据不可用或不完整，不得使用估算值冒充实际值。

**Phase 4 实装口径（已确认）：**
- 对话轮数 = 最近 7 天内用户消息条数（Execution 不计入）。
- Token = 最近 7 天 Assistant Message usage + Execution usage；两类记录对应不同模型调用，不重复计数。
- 两张统计卡均展示近 7 天逐日柱状图（日期 + 每日数值），总量显示在卡片大数字上。
- usage 完整性属于内部诊断信息：后端仍标记 tokens_complete，但**不向用户展示「数据不完整」**，避免暴露内部实现细节。

统计图表应简洁，作为辅助信息，不应占据首页主体。

### 3.3 最近项目

展示近期访问或更新的 Projects。

每个项目至少显示：
- 项目名称。
- 简短描述。
- 最近更新时间。
- 项目状态。

点击项目进入 Project 详情页。

### 3.4 最近任务

展示最近创建或更新的 Tasks。

每项展示：
- Task 标题。
- 所属 Project（如果有）。
- 当前状态。
- 最近活动时间。

点击任务进入对应 Task 工作区。

### 3.5 最近成果

展示近期生成的 Artifacts。

每项展示：
- 成果标题。
- 所属 Task 或 Project。
- 版本信息。
- 创建时间。

点击成果进入 Artifact 查看区域。

### 3.6 新建任务入口

提供清晰、易于发现的 New Task 入口。

入口采用适中尺寸，不需要过度突出或占据首页大面积空间。

新建任务时允许选择：
- 所属 Workspace（MVP 默认 Global Workspace）。
- 可选关联 Project。
- Task 标题和描述。
- 使用模型。

如果关联 Project，则自动应用 Project 文件继承规则。

## 4. Project 页面

Project 页面用于管理一个长期项目及其相关工作。

### 4.1 项目概览

展示：
- 项目名称和描述。
- 项目状态。
- 创建时间和最近更新时间。
- 项目下 Task 数量。
- 项目关联文件数量。
- 项目成果数量。

### 4.2 页面分区

建议采用 Tab 或清晰的页面分区：

- Overview：项目概览和最近活动。
- Tasks：项目下的任务列表。
- Files：项目关联文件。
- Artifacts：项目相关成果。

### 4.3 Project 文件管理

展示项目当前关联的文件。

支持：
- 从 Global Library 添加文件。
- 查看文件名称、类型、大小和添加时间。
- 移除项目文件关联。

移除关联不等于删除 Global Library 中的原始文件。

Project 文件是项目内 Task 的默认可用上下文来源。

### 4.4 Project Task

从 Project 页面创建 Task 时，自动关联当前 Project。

新建 Task 默认继承 Project 当前全部可用文件。具体调整方式见 Task Settings。

## 5. Task 工作区

> 注：Phase 3 实装后的 Chat / Artifacts / Execution 展示以 §14 为准；本节描述保留为原始设计基线。

Task 是 mousehole MVP 最重要的工作界面。

### 5.1 整体结构

Task 内部采用对话优先的布局，提供三个平级 Tab：

- **Chat**：对话内容、模型交互、Execution 状态与成果生成提示。
- **Settings**：当前 Task 的文件上下文、模型等配置。
- **Artifacts**：当前 Task 的成果系列与产出。

三个 Tab 平级，互不嵌套；Chat 是默认打开的主界面。Execution 进度通过 Chat 内的执行状态组件查看，不单独占用一级 Tab。

### 5.2 Task 顶部信息栏

展示：
- Task 标题。
- 所属 Project（如果有）。
- 当前 Task 状态。
- 当前使用的模型。
- 工作区页面切换入口。

允许用户通过模型选择入口更换当前 Task 使用的模型。

模型切换应影响后续模型调用，不得改变历史 Execution 已记录的模型信息。

### 5.3 Chat 页面（Conversation）

Chat 是 Task 的主要交互界面，对应 Conversation 实体。

布局和交互应接近成熟的 AI Chat 产品，但需要与 Task、Execution、Artifact 等实体保持关联。

主要组成：

1. 消息展示区域。
2. 用户输入区域。
3. 模型响应与流式输出。
4. Execution 状态展示。
5. Artifact 生成结果提示。

对话消息按照时间顺序展示，支持必要的 Markdown 内容渲染。

当 AI 生成 Artifact 时：
- 在当前对话中展示成果生成提示。
- 可以通过文件名或成果名称提供可访问的指针。
- 用户点击指针可以打开对应 Artifact。
- 不要求将完整 Artifact 内容重复塞入对话消息。

普通对话与复杂 Execution 的界限遵循 ARCHITECTURE.md 中的设计，不要求每一条 AI 回复都产生独立 Execution。

### 5.4 Artifacts 页面

Artifacts 与 Chat、Settings 平级，但不是 Task 默认展示页面。

该页面展示当前 Task 下的成果系列及其版本。

支持：
- 查看 ArtifactSeries。
- 查看每个系列的版本列表。
- 打开具体版本。
- 区分当前主要成果。
- 查看来源 Execution 编号和创建时间。

具体成果预览采用 Markdown 渲染。

Artifact 不仅是消息附件，而是独立保存、可再次访问的成果实体。

### 5.5 Settings 页面

Settings 与 Chat、Artifacts 平级，用于查看和调整当前 Task 的具体配置。

MVP 重点展示文件上下文。

文件上下文分为三类：

**项目继承文件**
- 来自所属 Project 的文件。
- 默认可用。
- 用户可以排除不需要的文件。

**额外引用文件**
- 用户从 Global Library 手动添加到当前 Task 的文件。
- 不依赖 Project 继承关系。

**已排除文件**
- 原本来自 Project 继承范围，但被当前 Task 排除的文件。
- 用户可以恢复使用。

支持从 Global Library 选择并额外添加文件。

同时展示：
- 当前可用文件总数。
- 每个文件的名称、类型和来源。
- 文件的继承或额外引用状态。
- 已排除文件及其状态。

必须向用户说明：

**可用文件不等于本次 Execution 实际读取的文件。**

Task Settings 展示的是可用上下文；具体 Execution 实际使用哪些文件，应在 Execution 详情中查看。

Global Workspace 中直接创建的 Task 不存在 Project 继承文件。

## 6. Execution 展示

> 注：Phase 3 实装后 Execution 不再单独成栏，仅在 Chat 内以「工作进度/运行详情」呈现（见 §14.4）。

Execution 是一次实际工作运行，应让用户理解当前运行状态、关键进度和最终结果。

### 6.1 运行状态

支持展示：
- Pending：等待执行。
- Running：执行中。
- Completed：执行成功。
- Failed：执行失败。
- Cancelled：已取消（如 MVP 支持取消操作）。

状态展示应具有明确的视觉区分。

### 6.2 关键阶段进度

Execution 运行时展示 Pipeline 关键阶段的实时进度：

1. Resolve Files：解析可用文件。
2. Parse Documents：解析文档。
3. Build Context：构建模型上下文。
4. Model Inference：模型推理。
5. Generate Artifact：生成成果。
6. Save Artifact：保存成果。
7. Complete：完成执行。

阶段进度来自后端 SSE 事件，状态包括 Pending / Running / Completed / Failed / Skipped（适用时）。

MVP 不持久化细粒度步骤：Execution 结束后只展示状态、结果摘要与错误信息，不提供逐步回放；完整步骤记录（ExecutionStep）属于 P1。

### 6.3 运行信息与错误

MVP 不持久化逐步执行日志，因此不提供历史日志回放。

- 运行期间：通过执行状态组件展示当前阶段与简要进度。
- 失败时：展示失败阶段、错误原因以及已完成和未完成的部分。
- 不展示底层调试信息；任何情况下都不得泄露 API Key、密码等敏感凭证。

详细运行日志属于开发调试能力，不进入用户界面。

### 6.4 Execution 历史

Task 内可以查看历史 Execution 列表。

每条记录至少展示：
- Execution 编号。
- 状态。
- 使用模型。
- 开始时间和结束时间。
- 生成的 Artifact 数量。

点击历史 Execution 可以查看状态、结果摘要、错误信息与实际使用文件快照；MVP 不展示逐步明细。

### 6.5 错误处理

错误展示必须遵循真实、透明的原则。

Execution 失败时：
- 明确展示 Failed 状态。
- 指明失败发生在哪个 Pipeline 阶段。
- 尽可能反馈具体错误原因。
- 说明失败前的执行进度（基于当前状态，不要求逐步明细）。
- 提供适当的重试入口。

不得将失败的 Execution 显示为成功。

不得在 Artifact 未成功保存时提示成果已经成功生成。

部分阶段已经完成时，应如实展示当前进度，不夸大也不隐瞒。

之前成功生成的 Artifacts 不受后续 Execution 失败影响。

## 7. Global Library 页面

Global Library 是统一文件资料库，负责管理原始文件。

### 7.1 文件列表

展示：
- 文件名称。
- 文件类型。
- 文件大小。
- 上传时间。
- 最近更新时间。

支持搜索和基本筛选。

### 7.2 文件操作

MVP 支持：
- 上传文件。
- 查看文件基本信息。
- 搜索文件。
- 查看文件被哪些 Project 或 Task 引用（实现成本允许时）。
- 删除未被保护的文件。

支持文件类型：
- PDF
- Markdown
- TXT

不支持的文件类型应明确提示，不得静默忽略。

删除操作需要考虑 Project、Task 和历史 Execution 的引用关系，不能破坏历史记录。

### 7.3 文件选择器

在创建 Project、创建 Task 或调整 Task Settings 时，允许打开 Global Library 文件选择器。

选择器应支持搜索、查看文件信息和选择多个文件。

文件选择只建立引用关系，不复制原始文件。

## 8. Artifact 详情

Artifact 应具有独立的查看体验。

### 8.1 内容展示

MVP 采用 Markdown 渲染，支持标题、列表、代码块、表格、引用等常见格式。

### 8.2 元数据

展示：
- Artifact 标题。
- 所属 ArtifactSeries。
- 当前版本号。
- 是否为当前主要成果。
- 来源 Execution。
- 创建时间。

### 8.3 版本切换

同一 ArtifactSeries 下展示版本列表。

用户可以打开不同版本，查看对应内容。

MVP 不实现版本差异比较、版本回滚和完整编辑历史。

## 9. 交互反馈规范

### 9.1 异步操作

上传文件、创建 Task、启动 Execution、保存 Artifact 等操作应提供清晰反馈。

对于耗时操作，应展示进行中状态，避免用户误以为系统没有响应。

### 9.2 流式响应

Conversation 支持模型流式响应。

Execution 的关键状态变化应及时反馈。

SSE 断开时，应允许页面重新获取 Execution 的最新状态，而不是直接认为执行失败。

### 9.3 操作确认

对删除文件、移除项目关联等可能影响用户资料的操作，提供适当的确认机制。

对于 MVP 尚未开放的高风险操作，不应仅通过隐藏按钮或前端限制来实现权限控制；后端仍须执行权限校验。

### 9.4 空状态

对于没有 Project、Task、Artifact 或文件的页面，提供清晰的空状态说明和相应入口。

空状态应告诉用户下一步可以做什么，而不是只展示空白区域。

## 10. 响应式与平台支持

MVP 仅支持桌面浏览器使用。

优先适配常见桌面分辨率，保证：
- 侧边栏能够正常展开和折叠。
- 主内容区域不会因布局拥挤而难以阅读。
- Task 对话和成果预览有足够的展示空间。
- 文件列表、Execution 状态与结果可以正常浏览。

MVP 不要求完整的手机端适配，也不要求提供独立移动端应用。

## 11. MVP 页面范围

| 页面 | MVP 支持内容 |
|---|---|
| Home | 问候语、日期、使用统计、最近 Project、Task、Artifact、新建任务 |
| Projects | 项目列表、项目详情、项目文件、项目 Task、项目成果 |
| Task / Chat | 对话、模型交互、Artifact 生成提示、Execution 状态 |
| Task / Artifacts | 成果系列、版本列表、成果查看 |
| Task / Settings | 项目继承文件、额外引用、排除文件、模型 |
| Execution Detail | 状态、实时阶段进度、结果摘要、错误、实际使用文件 |
| Global Library | 上传、搜索、文件列表、基本管理 |
| Artifact Detail | Markdown 预览、版本和来源信息 |
| Application Settings | 模型 Provider 配置（含已配置密钥的掩码查看与编辑）及必要的应用配置 |

## 12. 暂不实现的 UI 功能

MVP 暂不要求：
- 移动端完整适配。
- 浅色/暗色主题切换。
- 多窗口工作区。
- 自定义 Dashboard 布局。
- 高级数据分析和可视化面板。
- Execution 流程图编辑器。
- Execution 细粒度步骤持久化与历史日志回放（P1）。
- Agent Builder。
- Workflow 可视化编排。
- Artifact 版本差异比较。
- 多用户协作界面。
- 复杂的个性化主题和组件配置。

## 13. 与其他设计文档的关系

- PRODUCT_SPEC.md：定义产品定位和长期愿景。
- MVP_SPEC.md：定义 MVP 功能范围与验收标准。
- DATA_MODEL.md：定义 UI 中各类数据的实体和关系。
- TECHNICAL_DECISIONS.md：定义前端、后端和部署等技术选择。
- ARCHITECTURE.md：定义前后端模块职责和执行流程。
- UI_SPEC.md：定义用户如何通过界面访问和操作这些能力。

本文件定义交互结构和页面行为，不锁定具体组件库或 CSS 实现方式。

---

## 15. Phase 4 实装补充

### 15.1 Home

- 问候语使用通用称呼（不引入用户名称配置）；
- 统计卡：近 7 天对话轮数（用户消息条数）与 Token（Chat + Execution 实际 usage，缺失时标注不完整）；
- 最近 Projects / Tasks / Artifacts 三个区块；成果点击进入对应 Task 的 Artifacts Tab；
- 提供 New Task 入口。

### 15.2 Project

- 默认进入 Overview：Task / File / Artifact 数量 + 最近 Task / 最近成果；
- 保留 Tasks / Files / Artifacts 三个 Tab；
- 归档提示与原有操作不变。

### 15.3 Library

- 文件名搜索（防抖）；
- 类型筛选：全部 / PDF / Markdown / TXT / JSON / YAML / CSV / HTML / CSS；
- 基础排序：最近更新 / 文件名 / 文件大小；
- 删除仍先检查引用，引用中存在时返回 409。

### 15.4 Task Chat 运行历史

- 「工作进度」展示最近一次运行；
- 展开后提供默认折叠的「历史运行（N）」：状态、Skill、时间；不展示 Execution ID；
- 点击历史记录查看该次运行的关键阶段与实际使用文件。

### 15.5 Execution 展示原则

- Execution 继续作为内部运行管理实体；
- 用户界面使用「工作进度 / 运行历史」，不使用 Execution 编号作为主概念。

### 15.6 文件内容预览

- Project → Files：每行提供「预览」，弹窗显示文件元信息与解析文本；
- Task → Settings：可用/已排除文件行同样提供「预览」；
- Markdown 用渲染视图，PDF/TXT 用等宽文本视图；超长标注「已截断」。

### 15.7 流式输出

- 最终回答统一使用 SSE 增量渲染；
- 工具调用（保存成果、读取文件、启动执行）可能先经过非流式 pre-pass，但工具完成后会重新流式生成最终回答；
- 极短回答可能只有一两个 delta（内容不足缓冲区大小），属正常现象。

### 15.8 文件全文读取

- Chat 默认读取文件全文（≤2MB），不再按单文件 8k 字符截断；
- 文件预算随 Workspace context budget 调整（默认最多 64k tokens）；
- 只有总预算不足时才截断，并在上下文提示可用 `read_task_file` 分页读取剩余内容。

### 15.9 临时文件

- Chat 输入框「+」上传的文件是**单轮附件**：只随本次发送进入模型上下文；
- 不进入 Global Library，也不写入 Task 可用文件；发送后的下一轮不会自动携带；
- 消息上方显示「本轮临时」chips；发送后清空输入栏；移除附件或删除 Task 时清理（有历史快照时保留）。


---

## 14. Phase 3/4 实装补充（当前界面）

### 14.1 全局导航

- 左侧导航包含 **Home / All Tasks / Projects / Library / Skills / Settings**；
- All Tasks 是跨 Project 的任务索引，按 Global Workspace / Project 分组，Project 支持置顶与三点菜单（置顶 / 查看详情 / 删除）；
- Task 页面左侧提供 Project → Task 快速切换树，显示最近对话时间；
- Skill Library 支持新增、编辑、删除；名称必填，描述、指令 / 输出要求、System Prompt 均可选；
- 新建 Skill 时即可上传文件/文件夹，保存时统一上传并关联；文件夹导入会跳过不支持的文件并明确提示。

### 14.2 Task Chat

- Chat 为单一对话卡片，不再有独立文件/Skill 侧栏；
- 输入框左下角「+」：上传临时文件、引用 Skill、管理 Skill Library；
- Enter 发送，Shift+Enter 换行（IME 组合输入不误发）；
- 输入框上方 chips：本次临时文件 + 选中的 Skill；发送后自动清空；
- 模型与参数控件位于发送按钮左侧（模型选择 + Temperature / Max tokens / 上下文预算滑杆，默认 0.7 / 4096 / 32768）；
- 助手消息顶部显示**默认折叠的「思路链」**（工具步骤、结果、耗时）；运行中显示工作进度与思考/生成计时；
- Chat 内不展示 Artifact 入口或横幅。

### 14.3 Artifacts 页面

- 系列 / 版本列表 + Markdown 预览；
- 支持下载 Markdown、删除单个版本、重命名系列；
- 预览元数据显示来源：对话 / 运行 / 手动（不展示 Execution ID）。

### 14.4 Execution 展示

- 不单独设 Execution 栏或页面；
- 仅在 Chat 内以「工作进度 / 运行详情」折叠面板展示状态、关键阶段、实际使用文件与错误。

### 14.5 消息附件与来源

- 每条用户消息显示本次临时引入的 Skill/文件 chips（不列项目继承文件）；
- 每条助手消息显示其工具步骤与耗时（metadata），刷新后仍保留。


