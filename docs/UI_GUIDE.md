# UI_GUIDE.md — mousehole 界面与交互

**文档版本：** v0.3.0（Phase 6 规划中）  
**状态：** living（长期维护）  
**最后更新：** 2026-11-24  
**定位：** 页面地图、导航结构、关键交互规则与界面红线。**逐页字段与像素级细节以 `frontend/src` 和实际界面为准**，本文不复制组件清单。  
**相关文档：** `ROADMAP.md`（阶段规划）、`ARCHITECTURE.md`（模块）、`DATA_MODEL.md`（数据）。

---

## 1. 页面地图与导航

左侧导航（桌面）当前为：**Home / All Tasks / Projects / Library / Skills / Settings**；Phase 5 未新增 Artifacts 页面。

| 页面 | 路由 | 主要内容 |
|---|---|---|
| Home | `/` | 问候语、日期、7 天统计、最近 Projects/Tasks/Artifacts、新建任务入口 |
| All Tasks | `/tasks` | 跨 Project 任务索引，按 Global/Project 分组、置顶、筛选、三点菜单 |
| Projects | `/projects` | 项目账本式列表（Ledger）、归档 |
| Project Detail | `/projects/:id` | Overview（数量 + 最近活动）、Tasks / Files / Artifacts 三个 Tab；Files 支持本地上传（项目私有）与从 Library 添加 |
| Task | `/tasks/:id` | Chat / Settings / Artifacts 三个平级 Tab；左侧 Project → Task 快速切换树 |
| Library | `/library` | 全局文件：上传、文件名搜索、类型筛选、排序、预览、删除 |
| Skills | `/skills` | 全局 Skill 库：增删改查、文件/文件夹资料 |
| Settings | `/settings` | Provider 配置（测试连接、掩码显示）、应用配置 |

约定：桌面优先，**不做移动端完整适配**；暗色单主题；不引入重组件库，样式 token 统一。

---

## 2. 全局交互规范

### 2.1 状态与反馈

- 每个异步操作（上传、创建、执行、保存）必须有进行中/成功/失败反馈；长任务显示进度，不出现“假死”。
- 空状态要说明“下一步做什么”，并给出入口（新建任务、上传文件、创建项目）。
- 错误必须可见：展示错误码/原因，不把失败伪装成成功；SSE 断开时重新拉取状态，不直接判定失败。
- 破坏性操作（删除文件/成果、移除引用）需要确认。

### 2.2 信息呈现

- 列表与详情保持信息密度，避免大段说明文字；统计图（Home 7 天柱状图）按天展示。
- 成果来源使用「对话 / 运行 / 手动」表达，**不以 Execution ID 作为用户概念**。
- 不展示完整 Prompt、文件全文或 API Key；敏感信息仅掩码。

### 2.3 布局

- 主内容区保证对话与成果预览的阅读宽度；侧栏可折叠。
- Task 页面左侧树用于跨 Task 快速切换，显示最近对话时间。
- 字体、状态色、Tab 样式统一（暖墨编辑式风格，暗色单主题）。

---

## 3. Task 工作区

### 3.1 三个 Tab

- **Chat**：对话、模型交互、工作进度/历史运行、成果提醒。
- **Settings**：项目继承文件、额外引用、排除文件、模型与参数、文件预览。
- **Artifacts**：成果系列、版本列表、Markdown 预览、下载、存入 Library、删除。

### 3.2 Chat 输入区

- 输入框「+」：上传临时文件、引用 Skill、管理 Skill Library。
- 模型与参数控件位于发送按钮左侧：模型选择 + Temperature / Max tokens / 上下文预算滑杆；默认 0.7 / 4096 / 32768。
- Enter 发送，Shift+Enter 换行；IME 组合输入不误发。
- 输入框上方 chips：本轮临时文件 + 选中的 Skill；发送后清空（临时文件是**单轮附件**）。

### 3.3 消息与运行

- 用户消息展示本轮 Skill/文件 chips（不列项目继承文件）。
- 助手消息顶部默认折叠「思路链」：工具步骤、结果、耗时；刷新后仍保留（metadata）。
- 运行中显示工作进度与思考/生成计时；模型静默时发送心跳，避免“无输出”观感。
- 「历史运行」默认折叠：状态、Skill、时间；点击查看该次关键阶段与实际使用文件；不展示 Execution ID。
- 对话历史支持清空/恢复上下文：输入区上方显示状态条与按钮；清空后历史中插入分界线，明确“以上消息模型无法读取”，新消息落在下方。历史本身不删除。
- 历史条数默认 80 条消息（约 40 轮），由后端 `CHAT_HISTORY_LIMIT` 控制；超出的旧消息仍显示，但不进入模型。

### 3.4 成果提醒

- 生成成果后 Chat 内给出提醒；成果进入 Task Artifacts，不把聊天当成果存储。
- Chat 不展示独立 Execution 页面或栏位；暂不提供运行卡、上下文查看器、Diff。

---

## 4. Artifacts

- 按系列分组，展示版本列表、当前版本标记、来源（对话/运行/手动）。
- 支持 Markdown 预览、下载当前/指定版本、**存入 Library**、删除单版本、重命名系列。
- 「存入 Library」把当前版本的 Markdown 复制为普通 Library 文件；之后可在任意 Project/Task 引用；重复导出相同内容复用同一文件。
- 导出是快照：后续删除/改版本不影响已导出的 File。
- Phase 5 未实现：全局 Artifacts 页、成果编辑/切换当前版本、版本 Diff、从成果派生 Task。

---

## 5. 其他页面要点

| 页面 | 关键交互 |
|---|---|
| Home | 7 天对话轮数/Token 统计（usage 缺失时标注不完整）、最近 Projects/Tasks/Artifacts、New Task |
| Projects | 创建/编辑/归档；Overview 数量与最近活动；保留 Tasks/Files/Artifacts Tab |
| Project Detail → Files | 「从本地上传」只进入当前项目，不污染 Global Library，文件带「项目私有」标记；「从 Library 添加」引用全局文件；移除私有无引用文件会删除 |
| All Tasks | Global/Project 分组、置顶、筛选、三点菜单（置顶/详情/删除）；搜索仍为前端过滤，未做服务端分页（后置） |
| Library | 文件名搜索（防抖）、类型筛选、排序、预览、删除前引用检查；PDF 用浏览器原始页面预览，扫描版会提示缺少文本层/暂不支持 OCR |
| Skills | 名称必填；描述/指令/System Prompt 可选；创建时上传文件/文件夹，保留相对路径；内置「流程沉淀」可生成四段式技能卡，手动复制到新建表单 |
| Settings | Provider 选择、API Key 掩码编辑、测试连接；配置存本地，不入 Git |

---

## 6. Phase 5 已实现 UI（v0.3.0）

> 阶段规格见 `ROADMAP.md` §3；数据见 `DATA_MODEL.md` §5。

### 6.1 成果存入 Library

- Task → Artifacts → 选中版本后点「存入 Library」；成功后 toast 显示文件名。
- 导出文件可在 Library 搜索/预览，并作为普通文件被 Project/Task 引用。
- 没有全局 Artifacts 页；“成果复用”走 Library，不新增一级导航。

### 6.2 聊天上下文清空 / 恢复

- Chat 顶部状态条：显示当前是否已清空，并提供「清空上下文 / 恢复完整上下文」。
- 清空后历史中插入分界线：“上下文已清空：以上消息模型无法读取”；之后的新消息在下方。
- 不删除消息；恢复后分界线消失，模型重新按 `CHAT_HISTORY_LIMIT` 读取最近历史。
- 暂不提供“从某条消息重开”和多 Conversation。

### 6.3 流程沉淀 Skill

- 内置 Skill「流程沉淀」；在对话中引用后生成四段式 Markdown 技能卡（名称/描述/指令/System Prompt）。
- 用户手动复制到 Skills → 新建 Skill 的四个字段；本阶段不自动落库，暂无 `save_skill` 工具。

### 6.4 项目私有文件（交付后补充）

- Project → Files →「从本地上传」：文件只属于当前项目，不进入 Global Library；项目内 Task 默认继承。
- 文件列表标记「项目私有」；移除时提示“无其他引用会被删除”，与 Library 文件的“仅解除引用”不同。
- 「从 Library 添加」保留，引用全局文件。

### 6.5 后置的 UI（未实现）

- 全局 Artifacts 页；成果编辑/切换当前版本/版本 Diff/派生 Task。
- 运行卡、上下文查看器、取消/重跑入口。
- ⌘K 跨实体搜索、Task/Project 服务端搜索与分页、Prompt 模板、`save_skill`。

---

## 7. Phase 6 规划 UI（未实现）

- **OCR 进度**：上传扫描版 PDF 后显示页级进度、失败原因与重试入口；处理期间允许预览原始页面，但不提供“已可检索”的错误暗示。
- **Citation**：回答中的 `[S1]` 渲染为可点击 chip；点击打开原始 PDF 对应页或文本段落；无依据时明确显示“资料中未找到”。
- **文档页**：页级文本只作为派生数据展示，原文文件仍是唯一事实源。
- **检索开关**：长文档自动走检索；短文档继续全文，不做用户可见的复杂配置。
- **视觉升级**：等核心链路稳定后再统一做 design tokens / AppShell / 动效，避免与 OCR 主线同时开工。

---

## 8. 界面红线

1. 不展示 Execution ID 作为主概念；用「工作进度/运行历史」表达。
2. 失败/取消必须可见且可区分；不允许静默失败。
3. 长任务必须有进度与取消入口。
4. 空状态必须给下一步入口。
5. 不展示完整 Prompt、文件全文、API Key。
6. 桌面优先，不做移动端；暗色单主题；不引入组件库。
7. 页面组件不写复杂业务；HTTP 统一封装；跨页共享状态才进 Pinia。
