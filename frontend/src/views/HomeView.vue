<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import EmptyState from '@/components/EmptyState.vue'
import EntityMenu from '@/components/EntityMenu.vue'
import LoadingState from '@/components/LoadingState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  createTask,
  deleteProject,
  deleteTask,
  listProjects,
  listTasks,
  updateProject,
  updateTask,
} from '@/api/endpoints'
import type { Project, Task } from '@/api/types'
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
const loading = ref(true)
const projectsError = ref<string | null>(null)
const tasksError = ref<string | null>(null)
const creating = ref(false)

const recentProjects = computed(() => projects.value.slice(0, 5))
const recentTasks = computed(() => tasks.value.slice(0, 5))

const projectNames = computed(() => {
  const map = new Map<string, string>()
  for (const project of projects.value) map.set(project.id, project.name)
  return map
})

const usageStats = [
  {
    key: 'conversations',
    icon: 'chart',
    label: '近 7 天对话轮数',
    note: '对话与 Execution 统计将在 Phase 2 接入。',
  },
  {
    key: 'tokens',
    icon: 'database',
    label: '近 7 天 Token 消耗',
    note: '尚未接入模型 Provider 的 usage 数据。',
  },
]

const bothFailed = computed(() => Boolean(projectsError.value && tasksError.value))

async function load(): Promise<void> {
  loading.value = true
  projectsError.value = null
  tasksError.value = null
  const [projectResult, taskResult] = await Promise.allSettled([
    listProjects({ limit: 200 }),
    listTasks({ limit: 5 }),
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

    <section class="stats" aria-label="使用统计">
      <article v-for="stat in usageStats" :key="stat.key" class="card stat-card">
        <div class="stat-card__head">
          <span class="stat-card__icon"><AppIcon :name="stat.icon" :size="16" /></span>
          <span class="stat-card__label">{{ stat.label }}</span>
          <span class="chip chip--muted">不可用</span>
        </div>
        <p class="stat-card__value">暂无数据</p>
        <p class="stat-card__note">{{ stat.note }}</p>
      </article>
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
          <h2 class="section-title">最近 Projects</h2>
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
          <h2 class="section-title">最近 Tasks</h2>
          <span class="section-caption">按创建时间排序</span>
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
        <h2 class="section-title">最近成果</h2>
        <span class="section-caption">Phase 3 提供</span>
      </header>
      <EmptyState
        icon="file"
        title="成果功能尚未开放"
        description="Artifact 将在 Phase 3 提供，当前没有可展示的成果数据。"
        compact
      />
    </section>

  </div>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 8px 4px 12px;
}

.hero__date {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.02em;
}

.hero__greeting {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.25;
}

.hero__sub {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.hero__sub strong {
  font-weight: 600;
  color: var(--text);
}

.stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  padding: 14px 16px;
}

.stat-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-card__icon {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-muted);
}

.stat-card__label {
  font-size: 12px;
  color: var(--text-secondary);
}

.stat-card__head .chip {
  margin-left: auto;
}

.stat-card__value {
  margin: 10px 0 2px;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-muted);
}

.stat-card__note {
  margin: 0;
  font-size: 11.5px;
  color: var(--text-faint);
  line-height: 1.5;
}

.home-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.section-card {
  padding: 16px 4px 8px;
  overflow: hidden;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 16px 10px;
}

.section-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.section-link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  color: var(--text-muted);
}

.section-link:hover {
  color: var(--accent);
}

.section-caption {
  font-size: 11.5px;
  color: var(--text-faint);
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
  padding: 0 8px 8px;
}

.recent-list__item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.recent-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  padding: 10px;
  border-radius: var(--radius-sm);
  text-align: left;
  transition: background 0.13s ease;
}

.recent-row:hover {
  background: var(--bg-hover);
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
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-muted);
}

.recent-row__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.recent-row__title {
  font-size: 13px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-row__meta {
  font-size: 11.5px;
  color: var(--text-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (max-width: 980px) {
  .home-grid,
  .stats {
    grid-template-columns: minmax(0, 1fr);
  }

  .hero {
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }
}
</style>
