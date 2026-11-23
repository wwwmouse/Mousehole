# UI_GUIDE.md — mousehole 界面与交互

**文档版本：** v0.2.0-mvp  
**状态：** living（长期维护）  
**最后更新：** 2026-11-23  
**定位：** 页面地图、导航结构、关键交互规则与界面红线。**逐页字段与像素级细节以 `frontend/src` 和实际界面为准**，本文不复制组件清单。  
**相关文档：** `ROADMAP.md`（阶段规划）、`ARCHITECTURE.md`（模块）、`DATA_MODEL.md`（数据）。

---

## 1. 页面地图与导航

左侧导航（桌面）当前为：**Home / All Tasks / Projects / Library / Skills / Settings**（Phase 5 计划新增 **Artifacts**）。

| 页面 | 路由 | 主要内容 |
|---|---|---|
| Home | `/` | 问候语、日期、7 天统计、最近 Projects/Tasks/Artifacts、新建任务入口 |
| All Tasks | `/tasks` | 跨 Project 任务索引，按 Global/Project 分组、置顶、筛选、三点菜单 |
| Projects | `/projects` | 项目账本式列表（Ledger）、归档 |
| Project Detail | `/projects/:id` | Overview（数量 + 最近活动）、Tasks / Files / Artifacts 三个 Tab |
| Task | `/tasks/:id` | Chat / Settings / Artifacts 三个平级 Tab；左侧 Project → Task 快速切换树 |
| Library | `/library` | 全局文件：上传、文件名搜索、类型筛选、排序、预览、删除 |
| Skills | `/skills` | 全局 Skill 库：增删改查、文件/文件夹资料 |
| Settings | `/settings` | Provider 配置（测试连接、掩码显示）、应用配置 |
| Artifacts（Phase 5） | `/artifacts`、`/artifacts/:id` | 全局成果列表与独立详情（规划） |

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
- **Settings**：项目继承文件、额外引用、排除文件、模型与参数、文件预览（Phase 5 增加“引用成果”）。
- **Artifacts**：成果系列、版本列表、Markdown 预览、下载/删除。

### 3.2 Chat 输入区

- 输入框「+」：上传临时文件、引用 Skill、管理 Skill Library（Phase 5 增加“引用成果”）。
- 模型与参数控件位于发送按钮左侧：模型选择 + Temperature / Max tokens / 上下文预算滑杆；默认 0.7 / 4096 / 32768。
- Enter 发送，Shift+Enter 换行；IME 组合输入不误发。
- 输入框上方 chips：本轮临时文件 + 选中的 Skill；发送后清空（临时文件是**单轮附件**）。

### 3.3 消息与运行

- 用户消息展示本轮 Skill/文件 chips（不列项目继承文件）。
- 助手消息顶部默认折叠「思路链」：工具步骤、结果、耗时；刷新后仍保留（metadata）。
- 运行中显示工作进度与思考/生成计时；模型静默时发送心跳，避免“无输出”观感。
- 「历史运行」默认折叠：状态、Skill、时间；点击查看该次关键阶段与实际使用文件；不展示 Execution ID。
- 对话历史暂不支持新建/清空（Phase 5 用上下文重置点缓解，见 §6）。

### 3.4 成果提醒

- 生成成果后 Chat 内给出提醒；成果进入 Task Artifacts，不把聊天当成果存储。
- Chat 不展示独立 Execution 页面或栏位。

---

## 4. Artifacts

- 按系列分组，展示版本列表、当前版本标记、来源（对话/运行/手动）。
- 支持 Markdown 预览、下载当前/指定版本、删除单版本、重命名系列。
- 删除当前版本时按规则回退；被引用时不允许删除（Phase 5）。
- Phase 5 规划：独立详情页、编辑并新增版本、切换当前版本、版本 Diff、基于成果新建 Task、全局 Artifacts 页。

---

## 5. 其他页面要点

| 页面 | 关键交互 |
|---|---|
| Home | 7 天对话轮数/Token 统计（usage 缺失时标注不完整）、最近 Projects/Tasks/Artifacts、New Task |
| Projects | 创建/编辑/归档；Overview 数量与最近活动；保留 Tasks/Files/Artifacts Tab |
| All Tasks | Global/Project 分组、置顶、筛选、三点菜单（置顶/详情/删除）；无服务端搜索（Phase 5 补） |
| Library | 文件名搜索（防抖）、类型筛选、排序、预览、删除前引用检查 |
| Skills | 名称必填；描述/指令/System Prompt 可选；创建时上传文件/文件夹，保留相对路径 |
| Settings | Provider 选择、API Key 掩码编辑、测试连接；配置存本地，不入 Git |

---

## 6. Phase 5 规划 UI（未实现）

> 阶段规格见 `ROADMAP.md` §4；数据见 `DATA_MODEL.md` §5。

### 6.1 全局成果

- 导航新增 Artifacts；`/artifacts`：列表（标题/系列/当前版本/来源/所属 Project/Task/时间）、筛选、标题搜索、排序。
- `/artifacts/:id`：Markdown 渲染、版本列表、设为当前、编辑（创建新版本）、下载、删除、Diff、基于此新建 Task。

### 6.2 Task 引用成果

- 「+」新增“引用成果”选择器（按 Project/搜索）；chips 展示；发送后**不清空**（Task 级上下文）。
- Task Settings 增加“引用成果”区：钉住版本、“更新到最新”、移除；超预算时提示。

### 6.3 运行卡与上下文查看器

- Chat 内「工作进度/历史运行」展开为运行卡：模型/参数、Token 与成本（缺失显示“—（不完整）”）、材料清单、步骤时间线、产出成果、错误。
- 「查看上下文」：名称/类型/token/模式（直接/已摘要/已截断）/原因，顶部已用/预算；**不展示全文或 Prompt**。
- 操作：取消（Running）、重跑、查看 Diff、复制清单；不恢复独立 Execution 页面。

### 6.4 搜索与效率

- ⌘K 命令面板：Project/Task/File/Artifact/Message 分组，键盘上下选择、Enter 跳转。
- Tasks/Projects 增加搜索与加载更多，移除固定 200 条上限；Library 分页。
- 版本/运行 Diff：行级新增/删除高亮，长文档分块渲染。
- Prompt 模板入口（创建 Task/设置）与“保存为 Skill”。
- 对话上下文管理：清空上下文 / 从这里重开，历史用分割线标注模型不再读取。

---

## 7. 界面红线

1. 不展示 Execution ID 作为主概念；用「工作进度/运行历史」表达。
2. 失败/取消必须可见且可区分；不允许静默失败。
3. 长任务必须有进度与取消入口。
4. 空状态必须给下一步入口。
5. 不展示完整 Prompt、文件全文、API Key。
6. 桌面优先，不做移动端；暗色单主题；不引入组件库。
7. 页面组件不写复杂业务；HTTP 统一封装；跨页共享状态才进 Pinia。
