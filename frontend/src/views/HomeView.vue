<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatsBarChart from '@/components/StatsBarChart.vue'
import EntityMenu from '@/components/EntityMenu.vue'
import LoadingState from '@/components/LoadingState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  createTask,
  deleteProject,
  deleteTask,
  getStatsOverview,
  listFiles,
  listProjects,
  listTasks,
  updateProject,
  updateTask,
} from '@/api/endpoints'
import type { FileItem, Project, StatsOverview, Task } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'
import { formatDate, formatRelative, greeting } from '@/utils/format'

const router = useRouter()
const app = useAppStore()

const now = new Date()
const greetingText = greeting(now)
const dateText = formatDate(now)

const projects = ref<Project[]>([])
const tasks = ref<Task[]>([])
const files = ref<FileItem[]>([])
const stats = ref<StatsOverview | null>(null)
const loading = ref(true)
const projectsError = ref<string | null>(null)
const tasksError = ref<string | null>(null)
const statsError = ref<string | null>(null)
const creating = ref(false)

const recentProjects = computed(() => projects.value.slice(0, 5))
const recentTasks = computed(() => tasks.value.slice(0, 5))
const activeProjects = computed(
  () => projects.value.filter((project) => project.status !== 'archived').length,
)
const activeTasks = computed(
  () => tasks.value.filter((task) => task.status !== 'archived').length,
)
const libraryCount = computed(() => files.value.length)

const projectNames = computed(() => {
  const map = new Map<string, string>()
  for (const project of projects.value) map.set(project.id, project.name)
  return map
})

const recentArtifacts = computed(() => stats.value?.recent_artifacts ?? [])

function formatNumber(value: number | undefined): string {
  return (value ?? 0).toLocaleString('zh-CN')
}

const daily = computed(() => stats.value?.daily ?? [])
const dailyLabels = computed(() => daily.value.map((item) => item.date.slice(5)))
const activeStatKey = ref<'conversations' | 'tokens'>('conversations')

const usageStats = computed(() => [
  {
    key: 'conversations',
    icon: 'chart',
    label: '近 7 天对话轮数',
    value: stats.value ? formatNumber(stats.value.conversation_turns) : '—',
    note: '按天统计',
    series: daily.value.map((item) => item.conversation_turns),
    labels: dailyLabels.value,
    format: (value: number) => `${value} 轮`,
  },
  {
    key: 'tokens',
    icon: 'database',
    label: '近 7 天 Token 消耗',
    value: stats.value ? formatNumber(stats.value.tokens.total_tokens) : '—',
    note: '按天统计',
    series: daily.value.map((item) => item.total_tokens),
    labels: dailyLabels.value,
    format: (value: number) => `${formatNumber(value)} tokens`,
  },
])

const activeStat = computed(
  () =>
    usageStats.value.find((item) => item.key === activeStatKey.value) ??
    usageStats.value[0],
)

function setActiveStat(key: 'conversations' | 'tokens'): void {
  activeStatKey.value = key
}

function openArtifact(item: { task_id: string }): void {
  void router.push({
    name: 'task',
    params: { id: item.task_id },
    query: { tab: 'artifacts' },
  })
}

const bothFailed = computed(() => Boolean(projectsError.value && tasksError.value))

async function load(): Promise<void> {
  loading.value = true
  projectsError.value = null
  tasksError.value = null
  statsError.value = null
  const [projectResult, taskResult, statsResult, filesResult] =
    await Promise.allSettled([
      listProjects({ limit: 200 }),
      listTasks({ limit: 200 }),
      getStatsOverview(7),
      listFiles({ limit: 200 }),
    ])
  if (projectResult.status === 'fulfilled') {
    projects.value = projectResult.value
  } else {
    projectsError.value = errorMessage(projectResult.reason)
    projects.value = []
  }
  if (taskResult.status === 'fulfilled') {
    tasks.value = taskResult.value
  } else {
    tasksError.value = errorMessage(taskResult.reason)
    tasks.value = []
  }
  if (statsResult.status === 'fulfilled') {
    stats.value = statsResult.value
  } else {
    statsError.value = errorMessage(statsResult.reason)
    stats.value = null
  }
  if (filesResult.status === 'fulfilled') {
    files.value = filesResult.value
  } else {
    files.value = []
  }
  loading.value = false
}

function projectName(projectId: string | null): string {
  if (!projectId) return 'Global Workspace'
  return projectNames.value.get(projectId) ?? '关联 Project'
}

function openTask(task: Task): void {
  void router.push({ name: 'task', params: { id: task.id } })
}

async function createNewTask(): Promise<void> {
  if (creating.value) return
  creating.value = true
  try {
    const task = await createTask({ title: '未命名任务' })
    app.notify('success', '任务已创建')
    void router.push({ name: 'task', params: { id: task.id } })
  } catch (error) {
    app.notifyError(error)
  } finally {
    creating.value = false
  }
}

async function renameProject(project: Project, name: string): Promise<void> {
  try {
    await updateProject(project.id, { name })
    app.notify('success', '项目已重命名')
    await load()
  } catch (error) {
    app.notifyError(error)
  }
}

async function toggleProjectArchive(project: Project): Promise<void> {
  try {
    const next = project.status === 'archived' ? 'active' : 'archived'
    await updateProject(project.id, { status: next })
    app.notify('success', next === 'archived' ? '项目已归档' : '项目已取消归档')
    await load()
  } catch (error) {
    app.notifyError(error)
  }
}

async function removeProject(project: Project): Promise<void> {
  try {
    await deleteProject(project.id)
    app.notify('success', '项目「' + project.name + '」已删除')
    await load()
  } catch (error) {
    app.notifyError(error)
  }
}

async function renameTask(task: Task, name: string): Promise<void> {
  try {
    await updateTask(task.id, { title: name })
    app.notify('success', '任务已重命名')
    await load()
  } catch (error) {
    app.notifyError(error)
  }
}

async function toggleTaskArchive(task: Task): Promise<void> {
  try {
    const next = task.status === 'archived' ? 'active' : 'archived'
    await updateTask(task.id, { status: next })
    app.notify('success', next === 'archived' ? '任务已归档' : '任务已取消归档')
    await load()
  } catch (error) {
    app.notifyError(error)
  }
}

async function removeTask(task: Task): Promise<void> {
  try {
    await deleteTask(task.id)
    app.notify('success', '任务「' + task.title + '」已删除')
    await load()
  } catch (error) {
    app.notifyError(error)
  }
}

onMounted(() => {
  void load()
  void app.loadWorkspace()
})
</script>

<template>
  <div class="home">
    <section class="hero">
      <div class="hero__main">
        <p class="hero__date">{{ dateText }}</p>
        <h1 class="hero__greeting">{{ greetingText }}</h1>
        <p class="hero__sub">
          <template v-if="app.currentWorkspace">
            欢迎回到 <strong>{{ app.currentWorkspace.name }}</strong>。继续推进你的项目与任务。
          </template>
          <template v-else>欢迎回到你的工作空间。继续推进你的项目与任务。</template>
        </p>
      </div>
      <button type="button" class="btn btn--primary" :disabled="creating" @click="createNewTask">
        <span v-if="creating" class="spinner spinner--sm" aria-hidden="true" />
        <AppIcon v-else name="plus" :size="16" />
        {{ creating ? '创建中…' : 'New Task' }}
      </button>
    </section>

    <section class="overview" aria-label="使用统计与活跃概况">
      <div class="overview-panel overview-panel--chart">
        <header class="overview-panel__head">
          <div class="stat-switch" role="tablist" aria-label="统计指标">
            <button
              type="button"
              class="stat-switch__item"
              :class="{ 'stat-switch__item--active': activeStatKey === 'conversations' }"
              role="tab"
              :aria-selected="activeStatKey === 'conversations'"
              @click="setActiveStat('conversations')"
            >
              对话轮数
            </button>
            <button
              type="button"
              class="stat-switch__item"
              :class="{ 'stat-switch__item--active': activeStatKey === 'tokens' }"
              role="tab"
              :aria-selected="activeStatKey === 'tokens'"
              @click="setActiveStat('tokens')"
            >
              Token
            </button>
          </div>
          <div class="overview-panel__heading">
            <span class="overview-panel__eyebrow">LAST 7 DAYS</span>
            <h2 class="overview-panel__title">{{ activeStat.label }}</h2>
          </div>
          <span class="overview-panel__value">{{ activeStat.value }}</span>
        </header>
        <StatsBarChart
          v-if="stats && !statsError"
          :values="activeStat.series"
          :labels="activeStat.labels"
          :format="activeStat.format"
        />
        <p class="overview-panel__note">{{ statsError ?? activeStat.note }}</p>
      </div>

      <aside class="overview-panel overview-panel--activity">
        <header class="overview-panel__head overview-panel__head--activity">
          <div class="overview-panel__heading">
            <span class="overview-panel__eyebrow">ACTIVE NOW</span>
            <h2 class="overview-panel__title">最近活跃</h2>
          </div>
        </header>
        <ul class="activity-list">
          <li>
            <span class="activity-list__label">
              <span class="activity-list__en">Tasks</span>
              <span class="activity-list__cn">未归档任务</span>
            </span>
            <strong class="activity-list__value">{{ activeTasks }}</strong>
          </li>
          <li>
            <span class="activity-list__label">
              <span class="activity-list__en">Projects</span>
              <span class="activity-list__cn">未归档项目</span>
            </span>
            <strong class="activity-list__value">{{ activeProjects }}</strong>
          </li>
          <li>
            <span class="activity-list__label">
              <span class="activity-list__en">Library</span>
              <span class="activity-list__cn">资料库文件总数</span>
            </span>
            <strong class="activity-list__value">{{ libraryCount }}</strong>
          </li>
        </ul>
      </aside>
    </section>

    <div v-if="bothFailed" class="panel panel--error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">数据加载失败</p>
        <p class="panel--error__desc">{{ projectsError }}</p>
      </div>
      <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
    </div>

    <div class="home-grid">
      <section class="card section-card">
        <header class="section-head">
          <div class="section-heading">
            <h2 class="section-title">最近 Projects</h2>
            <span class="section-count">{{ activeProjects }}</span>
          </div>
          <RouterLink to="/projects" class="section-link">
            查看全部
            <AppIcon name="chevron-right" :size="13" />
          </RouterLink>
        </header>
        <LoadingState v-if="loading" compact />
        <div v-else-if="projectsError" class="section-error">
          <p>{{ projectsError }}</p>
          <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
        </div>
        <EmptyState
          v-else-if="recentProjects.length === 0"
          icon="folder"
          title="还没有 Project"
          description="创建一个 Project，把长期跟进的资料和任务组织在一起。"
          compact
        >
          <RouterLink to="/projects" class="btn btn--ghost btn--sm">前往 Projects</RouterLink>
        </EmptyState>
        <ul v-else class="recent-list">
          <li v-for="project in recentProjects" :key="project.id" class="recent-list__item">
            <RouterLink :to="`/projects/${project.id}`" class="recent-row">
              <span class="recent-row__icon"><AppIcon name="folder" :size="15" /></span>
              <span class="recent-row__main">
                <span class="recent-row__title">{{ project.name }}</span>
                <span class="recent-row__meta">
                  {{ project.task_count }} 个 Task · {{ project.file_count }} 个文件 · 更新于
                  {{ formatRelative(project.updated_at) }}
                </span>
              </span>
              <StatusBadge :status="project.status" kind="project" />
            </RouterLink>
            <EntityMenu
              kind="project"
              :name="project.name"
              :archived="project.status === 'archived'"
              @rename="(name) => renameProject(project, name)"
              @toggle-archive="toggleProjectArchive(project)"
              @remove="removeProject(project)"
            />
          </li>
        </ul>
      </section>

      <section class="card section-card">
        <header class="section-head">
          <div class="section-heading">
            <h2 class="section-title">最近 Tasks</h2>
            <span class="section-count">{{ activeTasks }}</span>
          </div>
          <RouterLink to="/tasks" class="section-link">
            查看全部
            <AppIcon name="chevron-right" :size="13" />
          </RouterLink>
        </header>
        <LoadingState v-if="loading" compact />
        <div v-else-if="tasksError" class="section-error">
          <p>{{ tasksError }}</p>
          <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
        </div>
        <EmptyState
          v-else-if="recentTasks.length === 0"
          icon="sparkles"
          title="还没有 Task"
          description="创建一个 Task，开始一次有明确目标的工作。"
          compact
        >
          <button type="button" class="btn btn--ghost btn--sm" :disabled="creating" @click="createNewTask">
            <span v-if="creating" class="spinner spinner--sm" aria-hidden="true" />
            {{ creating ? '创建中…' : '新建 Task' }}
          </button>
        </EmptyState>
        <ul v-else class="recent-list">
          <li v-for="task in recentTasks" :key="task.id" class="recent-list__item">
            <button type="button" class="recent-row recent-row--button" @click="openTask(task)">
              <span class="recent-row__icon"><AppIcon name="sparkles" :size="15" /></span>
              <span class="recent-row__main">
                <span class="recent-row__title">{{ task.title }}</span>
                <span class="recent-row__meta">
                  {{ projectName(task.project_id) }} · 更新于 {{ formatRelative(task.updated_at) }}
                </span>
              </span>
              <StatusBadge :status="task.status" kind="task" />
            </button>
            <EntityMenu
              kind="task"
              :name="task.title"
              :archived="task.status === 'archived'"
              @rename="(name) => renameTask(task, name)"
              @toggle-archive="toggleTaskArchive(task)"
              @remove="removeTask(task)"
            />
          </li>
        </ul>
      </section>
    </div>

    <section class="card section-card">
      <header class="section-head">
        <div class="section-heading">
          <h2 class="section-title">最近成果</h2>
          <span class="section-count">{{ recentArtifacts.length }}</span>
        </div>
        <span class="section-caption">最近 5 条</span>
      </header>
      <LoadingState v-if="loading" compact />
      <div v-else-if="statsError" class="section-error">
        <p>{{ statsError }}</p>
        <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
      </div>
      <EmptyState
        v-else-if="recentArtifacts.length === 0"
        icon="file"
        title="还没有成果"
        description="在 Task 中让 AI 生成并保存成果后，会在这里出现。"
        compact
      >
        <button type="button" class="btn btn--ghost btn--sm" :disabled="creating" @click="createNewTask">
          新建 Task
        </button>
      </EmptyState>
      <div v-else class="artifact-ledger">
        <div class="artifact-ledger__head" aria-hidden="true">
          <span>成果</span>
          <span>Task</span>
          <span>Project</span>
          <span>版本</span>
          <span>更新时间</span>
          <span />
        </div>
        <button
          v-for="item in recentArtifacts"
          :key="item.artifact_id"
          type="button"
          class="artifact-ledger__row"
          @click="openArtifact(item)"
        >
          <span class="artifact-ledger__title" :title="item.title">{{ item.title }}</span>
          <span class="artifact-ledger__cell" :title="item.task_title">{{ item.task_title }}</span>
          <span class="artifact-ledger__cell" :title="item.project_name ?? 'Global Workspace'">
            {{ item.project_name ?? 'Global Workspace' }}
          </span>
          <span class="artifact-ledger__cell">v{{ item.version }}</span>
          <span class="artifact-ledger__cell">{{ formatRelative(item.created_at) }}</span>
          <AppIcon name="chevron-right" :size="14" class="artifact-ledger__chevron" />
        </button>
      </div>
    </section>

  </div>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: 26px;
}

.hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 2px 2px 4px;
}

.hero__date {
  margin: 0 0 10px;
  font-family: var(--font-mono);
  font-size: 12px;
  text-transform: uppercase;
  color: var(--text-secondary);
  letter-spacing: 0.1em;
}

.hero__greeting {
  margin: 0;
  font-family: var(--font-display);
  font-size: 46px;
  font-weight: 600;
  letter-spacing: -0.04em;
  line-height: 1.08;
}

.hero__sub {
  margin: 10px 0 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.hero__sub strong {
  font-weight: 600;
  color: var(--text);
}

.overview {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(260px, 0.75fr);
  gap: 32px;
  padding: 18px 0 16px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  align-items: stretch;
}

.overview-panel {
  min-width: 0;
}

.overview-panel--chart {
  display: flex;
  flex-direction: column;
  padding-right: 32px;
  border-right: 1px solid var(--border);
}

.overview-panel__head {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 10px;
}

.overview-panel__head--activity {
  margin-bottom: 0;
}

.stat-switch {
  display: inline-flex;
  flex-shrink: 0;
  gap: 2px;
  padding: 2px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.stat-switch__item {
  padding: 5px 9px;
  border: 0;
  border-radius: 2px;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.03em;
  cursor: pointer;
}

.stat-switch__item:hover {
  color: var(--text);
}

.stat-switch__item--active {
  background: var(--accent);
  color: #1b120d;
}

.overview-panel__heading {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.overview-panel__eyebrow {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.overview-panel__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.15;
  color: var(--text);
}

.overview-panel__value {
  margin-left: auto;
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1;
  color: var(--text);
  white-space: nowrap;
}

.overview-panel__note {
  margin: 10px 0 0;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.03em;
  color: var(--text-muted);
  line-height: 1.5;
}

.activity-list {
  list-style: none;
  margin: 14px 0 0;
  padding: 0;
}

.activity-list li {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px solid var(--border);
}

.activity-list li:last-child {
  border-bottom: 0;
}

.activity-list__label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.activity-list__en {
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.activity-list__cn {
  font-size: 12.5px;
  letter-spacing: 0.01em;
  color: var(--text-muted);
}

.activity-list__value {
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1;
  color: var(--text);
}

.home-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 32px;
}

.section-card {
  padding: 16px 0 0;
  border: 0;
  border-top: 1px solid var(--border);
  border-radius: 0;
  background: transparent;
  overflow: hidden;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 0 2px 10px;
}

.section-heading {
  display: flex;
  align-items: baseline;
  gap: 9px;
}

.section-count {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
}

.section-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--font-size-section);
  font-weight: 600;
  letter-spacing: -0.015em;
  color: var(--text);
}

.section-link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.section-link:hover {
  color: var(--accent);
}

.section-caption {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.section-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 16px 16px;
  color: var(--danger);
  font-size: 12.5px;
}

.section-error p {
  margin: 0;
}

.recent-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.artifact-ledger {
  margin: 0 2px;
}

.artifact-ledger__head,
.artifact-ledger__row {
  display: grid;
  grid-template-columns:
    minmax(0, 2.6fr) minmax(0, 1.5fr) minmax(0, 1.2fr)
    54px 112px 16px;
  gap: 18px;
  align-items: center;
}

.artifact-ledger__head {
  padding: 0 2px 9px;
  border-bottom: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.artifact-ledger__row {
  width: 100%;
  padding: 15px 2px;
  border: 0;
  border-bottom: 1px solid var(--border);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.13s ease;
}

.artifact-ledger__row:hover {
  background: var(--bg-subtle);
}

.artifact-ledger__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.015em;
  color: var(--text);
}

.artifact-ledger__cell {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--text-secondary);
}

.artifact-ledger__chevron {
  color: var(--text-muted);
}

.recent-list__item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.recent-row {
  display: flex;
  align-items: center;
  gap: 11px;
  flex: 1;
  min-width: 0;
  padding: 12px 2px;
  border-bottom: 1px solid var(--border);
  border-radius: 0;
  text-align: left;
  transition: border-color 0.13s ease, background 0.13s ease;
}

.recent-row:hover {
  background: var(--bg-subtle);
  border-bottom-color: var(--border-strong);
}

.recent-row--button {
  border: none;
  background: transparent;
  cursor: pointer;
  font: inherit;
  color: inherit;
}

.recent-row__icon {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--accent);
}

.recent-row__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.recent-row__title {
  font-size: 14px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-row__meta {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (max-width: 980px) {
  .home-grid,
  .overview {
    grid-template-columns: minmax(0, 1fr);
  }

  .overview {
    gap: 18px;
  }

  .overview-panel--chart {
    padding-right: 0;
    padding-bottom: 16px;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }

  .hero {
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }
}
</style>
