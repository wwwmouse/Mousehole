# mousehole

> 面向个人用户的 **Local-first AI Workspace**：把资料、任务、执行过程和成果沉淀在同一个持续存在的工作空间里。

**状态：Phase 4 已完成（MVP 功能验收通过）。** 当前进入维护/打磨阶段。

## 核心闭环

```text
创建 Project → 上传多份资料 → 创建 Task → 组织上下文
      → 模型分析 → 生成 Markdown Artifact → 重启后继续复用
```

- Workspace → Project → Task → Execution → Artifact；
- File 提供资料，Conversation 记录交流；
- 纯本地优先，数据默认保存在本机。

## 快速开始（Docker，推荐）

### 第一次启动

前提：安装并启动 Docker Desktop；本机 8090 端口可用。

```powershell
cd E:\VScode\Mousehole
copy .env.example .env        # 环境变量模板；.env 不入 Git
docker compose up -d --build  # 构建镜像并后台启动全部服务
```

打开 **http://localhost:8090**。首次启动会自动执行数据库迁移并创建默认 Workspace。

首次使用还需要在 **Settings** 配置 Provider（DeepSeek / OpenAI / Ollama）并点「测试连接」；API Key 保存在本机 `data/provider_config.json`，接口只返回掩码。

### 日常使用（重点）

**第一次启动成功后，以后只需要保证 Docker Desktop 正在运行，然后打开 8090 即可，不用敲任何命令。**

- 三个容器都使用 `restart: unless-stopped`，Docker 启动时会自动恢复；
- 如果执行过 `docker compose stop` 或 `down`，需要执行一次 `docker compose up -d`；
- 改代码后需要 `docker compose up -d --build`；
- 永远不要执行 `docker compose down -v`（会删除数据库卷）。

### 常用 Docker 命令

```powershell
docker compose up -d --build   # 改代码后：重建镜像并启动
docker compose up -d           # 启动已有容器（不重建）
docker compose ps              # 查看容器状态与端口
docker compose logs -f backend # 跟踪后端日志
docker compose stop            # 停止容器，保留数据
docker compose start           # 启动已停止的容器
docker compose down            # 删除容器，保留数据卷
```

- 只更新 Docker Desktop：容器通常会自动恢复；没起来就执行一次 `docker compose up -d`；
- 更新代码：`docker compose up -d --build`；
- 更新 PostgreSQL 镜像（可选）：先备份，再 `docker compose pull postgres`、`docker compose up -d`。

### 开发模式（热更新）

生产模式和开发模式共用 project name 与数据卷，**不要同时启动**。

```powershell
docker compose down
docker compose -f docker-compose.dev.yml up -d
# 前端 http://localhost:5173，后端 http://localhost:8000，保存代码自动热更新
```

回到生产模式：

```powershell
docker compose -f docker-compose.dev.yml down
docker compose up -d
```

### 数据与备份

| 数据 | 位置 |
|---|---|
| 数据库 | Docker 卷 `mousehole_pgdata` |
| 上传文件 | `storage/` |
| Provider 配置/API Key | `data/provider_config.json`（明文，勿提交） |
| 备份 | `backups/<timestamp>/` |

```powershell
.\scripts\backup.ps1                                      # 备份数据库 + storage
.\scripts\restore.ps1 -BackupDir .\backups\<时间戳> -Force  # 覆盖恢复
```

备份默认不包含 Provider API Key，恢复后需要在 Settings 重新填写。

## 测试

```powershell
# 后端
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q       # 当前 104 passed

# 前端构建
cd ..\frontend
npm run build

# Playwright E2E（需 Docker 8090 运行；Mock API，不调用真实模型）
npm run test:e2e                                      # 当前 2 passed
```

E2E 默认使用系统 Edge（`channel: 'msedge'`）；无 Edge 时执行 `npx playwright install chromium` 并调整 `playwright.config.ts`。

## 主要能力

- Project / Task / File 管理，PDF、Markdown、TXT 解析，文件继承与引用保护；
- Task Chat：SSE 流式输出、临时文件单轮引用、Skill 引用、受控工具调用；
- Execution：确定性 Pipeline、状态/阶段进度、取消、文件快照、失败显式；
- Artifact：独立版本化成果，支持下载与删除；
- Home 统计（7 天柱状图）、Project Overview、Library 搜索/筛选/排序；
- Docker 生产/开发交付、数据持久化、备份恢复、Playwright E2E。

## 文档

- [产品与 MVP 范围](docs/PRODUCT_SPEC.md) · [MVP 规范](docs/MVP_SPEC.md)
- [数据模型](docs/DATA_MODEL.md) · [技术决策](docs/TECHNICAL_DECISIONS.md)
- [架构](docs/ARCHITECTURE.md) · [UI 规范](docs/UI_SPEC.md)
- [开发计划与验收记录](docs/DEVELOPMENT_PLAN.md)
- [Agent 开发约束](AGENTS.md)

## 边界

- 个人本地工具，不做多用户/权限/SaaS；
- MVP 不做 RAG/向量检索、多 Agent、任意 Shell、Office 解析；
- 极多长文件合计超过 Chat 文件预算时仍会截断，可用 `read_task_file` 分页读取；
- UI 视觉细节仍可继续打磨。

## 许可证

未确定。在项目负责人选定许可证前，请勿对外分发或复用本项目代码。
