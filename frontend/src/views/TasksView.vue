<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import EntityMenu from '@/components/EntityMenu.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  createTask,
  deleteProject,
  deleteTask,
  listProjects,
  listTasks,
  updateTask,
} from '@/api/endpoints'
import type { Project, Task, TaskStatus } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'
import { formatRelative } from '@/utils/format'
import {
  readPinnedProjects,
  togglePinnedProject,
} from '@/utils/projectPins'

const router = useRouter()
const app = useAppStore()

const tasks = ref<Task[]>([])
const projects = ref<Project[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const search = ref('')
const statusFilters = ref<Array<'active' | 'archived'>>([])
const scopeFilters = ref<Array<'global' | 'project'>>([])
const filterOpen = ref(false)
const expandedGroups = ref<string[]>([])
const pinnedProjects = ref<string[]>(readPinnedProjects())
const deleteProjectTarget = ref<{ id: string; name: string } | null>(null)
const deletingProject = ref(false)
const openGroupMenu = ref<string | null>(null)
const creating = ref(false)

const activeFilterCount = computed(
  () => statusFilters.value.length + scopeFilters.value.length,
)

function toggleStatus(status: 'active' | 'archived'): void {
  statusFilters.value = statusFilters.value.includes(status)
    ? statusFilters.value.filter((item) => item !== status)
    : [...statusFilters.value, status]
}

function toggleScope(scope: 'global' | 'project'): void {
  scopeFilters.value = scopeFilters.value.includes(scope)
    ? scopeFilters.value.filter((item) => item !== scope)
    : [...scopeFilters.value, scope]
}

function isExpanded(key: string): boolean {
  return expandedGroups.value.includes(key)
}

function toggleGroup(key: string): void {
  expandedGroups.value = isExpanded(key)
    ? expandedGroups.value.filter((item) => item !== key)
    : [...expandedGroups.value, key]
}

function clearFilters(): void {
  search.value = ''
  statusFilters.value = []
  scopeFilters.value = []
}

const projectNames = computed(() => {
  const map = new Map<string, string>()
  for (const project of projects.value) map.set(project.id, project.name)
  return map
})

const activeCount = computed(
  () => tasks.value.filter((task) => task.status !== 'archived').length,
)

const visibleTasks = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return tasks.value.filter((task) => {
    const status = task.status as 'active' | 'archived'
    if (statusFilters.value.length && !statusFilters.value.includes(status)) return false
    const scope = task.project_id ? 'project' : 'global'
    if (scopeFilters.value.length && !scopeFilters.value.includes(scope)) return false
    if (!keyword) return true
    const project = task.project_id
      ? (projectNames.value.get(task.project_id) ?? '')
      : 'Global Workspace'
    return (
      task.title.toLowerCase().includes(keyword) ||
      (task.description ?? '').toLowerCase().includes(keyword) ||
      project.toLowerCase().includes(keyword)
    )
  })
})

const globalTasks = computed(() =>
  visibleTasks.value.filter((task) => !task.project_id),
)

const projectGroups = computed(() => {
  const groups = new Map<string, Task[]>()
  for (const task of visibleTasks.value) {
    if (!task.project_id) continue
    const list = groups.get(task.project_id) ?? []
    list.push(task)
    groups.set(task.project_id, list)
  }
  return Array.from(groups.entries())
    .map(([projectId, items]) => ({
      projectId,
      projectName: projectNames.value.get(projectId) ?? '关联 Project',
      tasks: items,
    }))
    .sort((a, b) => {
      const aPinned = pinnedProjects.value.includes(a.projectId)
      const bPinned = pinnedProjects.value.includes(b.projectId)
      if (aPinned !== bPinned) return aPinned ? -1 : 1
      return a.projectName.localeCompare(b.projectName, 'zh-CN')
    })
})

function isProjectPinned(projectId: string): boolean {
  return pinnedProjects.value.includes(projectId)
}

function toggleProjectPin(projectId: string): void {
  pinnedProjects.value = togglePinnedProject(pinnedProjects.value, projectId)
  openGroupMenu.value = null
}

function toggleGroupMenu(projectId: string): void {
  openGroupMenu.value = openGroupMenu.value === projectId ? null : projectId
}

function viewGroupProject(projectId: string): void {
  openGroupMenu.value = null
  void router.push('/projects/' + projectId)
}

function requestDeleteProject(project: { projectId: string; projectName: string }): void {
  openGroupMenu.value = null
  deleteProjectTarget.value = { id: project.projectId, name: project.projectName }
}

async function confirmDeleteProject(): Promise<void> {
  const target = deleteProjectTarget.value
  if (!target) return
  deletingProject.value = true
  try {
    await deleteProject(target.id)
    pinnedProjects.value = pinnedProjects.value.filter((id) => id !== target.id)
    deleteProjectTarget.value = null
    app.notify('success', '项目「' + target.name + '」已删除')
    await load()
  } catch (err) {
    app.notifyError(err)
  } finally {
    deletingProject.value = false
  }
}

function modelLabel(task: Task): string {
  if (!task.model_provider || !task.model_name) return '未配置模型'
  return task.model_provider + ' / ' + task.model_name
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [taskResult, projectResult] = await Promise.all([
      listTasks({ limit: 200 }),
      listProjects({ limit: 200 }),
    ])
    tasks.value = taskResult
    projects.value = projectResult
  } catch (err) {
    error.value = errorMessage(err)
    tasks.value = []
  } finally {
    loading.value = false
  }
}

async function createNewTask(): Promise<void> {
  if (creating.value) return
  creating.value = true
  try {
    const task = await createTask({ title: '未命名任务' })
    app.notify('success', '任务已创建')
    void router.push({ name: 'task', params: { id: task.id } })
  } catch (err) {
    app.notifyError(err)
  } finally {
    creating.value = false
  }
}

async function renameTask(task: Task, title: string): Promise<void> {
  try {
    await updateTask(task.id, { title })
    app.notify('success', '任务已重命名')
    await load()
  } catch (err) {
    app.notifyError(err)
  }
}

async function toggleArchive(task: Task): Promise<void> {
  try {
    const next: TaskStatus = task.status === 'archived' ? 'active' : 'archived'
    await updateTask(task.id, { status: next })
    app.notify('success', next === 'archived' ? '任务已归档' : '任务已取消归档')
    await load()
  } catch (err) {
    app.notifyError(err)
  }
}

async function removeTask(task: Task): Promise<void> {
  try {
    await deleteTask(task.id)
    app.notify('success', '任务「' + task.title + '」已删除')
    await load()
  } catch (err) {
    app.notifyError(err)
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="tasks-view">
    <PageHeader
      title="All Tasks"
      description="按 Global Workspace 与 Project 分组的 Task 索引。"
    >
      <template #actions>
        <button type="button" class="btn btn--primary" :disabled="creating" @click="createNewTask">
          <span v-if="creating" class="spinner spinner--sm" aria-hidden="true" />
          <AppIcon v-else name="plus" :size="16" />
          {{ creating ? '创建中…' : '新建 Task' }}
        </button>
      </template>
    </PageHeader>

    <div class="tasks-toolbar">
      <label class="search-box">
        <AppIcon name="search" :size="15" />
        <input
          v-model="search"
          class="search-box__input"
          type="search"
          placeholder="搜索 Task 标题、描述或 Project…"
        />
      </label>
      <div class="filter-wrap">
        <button
          type="button"
          class="filter-trigger"
          :class="{ 'filter-trigger--active': activeFilterCount > 0 || filterOpen }"
          @click="filterOpen = !filterOpen"
        >
          <AppIcon name="filter" :size="14" />
          筛选
          <span v-if="activeFilterCount" class="filter-trigger__badge">{{ activeFilterCount }}</span>
        </button>

        <div v-if="filterOpen" class="filter-backdrop" @click="filterOpen = false" />
        <div v-if="filterOpen" class="filter-popover" @click.stop>
          <section class="filter-section">
            <h3 class="filter-section__title">状态</h3>
            <label class="filter-option">
              <input
                type="checkbox"
                :checked="statusFilters.includes('active')"
                @change="toggleStatus('active')"
              />
              <span>进行中</span>
            </label>
            <label class="filter-option">
              <input
                type="checkbox"
                :checked="statusFilters.includes('archived')"
                @change="toggleStatus('archived')"
              />
              <span>已归档</span>
            </label>
          </section>

          <section class="filter-section">
            <h3 class="filter-section__title">范围</h3>
            <label class="filter-option">
              <input
                type="checkbox"
                :checked="scopeFilters.includes('project')"
                @change="toggleScope('project')"
              />
              <span>Project 内 Task</span>
            </label>
            <label class="filter-option">
              <input
                type="checkbox"
                :checked="scopeFilters.includes('global')"
                @change="toggleScope('global')"
              />
              <span>全局 Task</span>
            </label>
          </section>

          <button type="button" class="filter-clear" @click="clearFilters">
            <AppIcon name="refresh" :size="13" />
            清空筛选
          </button>
        </div>
      </div>
      <span class="toolbar__count">{{ activeCount }} 个活跃 / {{ tasks.length }} 个 Task</span>
    </div>

    <LoadingState v-if="loading" label="正在加载 Task…" />

    <div v-else-if="error" class="panel panel--error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">Task 加载失败</p>
        <p class="panel--error__desc">{{ error }}</p>
      </div>
      <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
    </div>

    <EmptyState
      v-else-if="tasks.length === 0"
      icon="flag"
      title="还没有 Task"
      description="创建一个 Task，开始一次有明确目标的工作。"
    >
      <button type="button" class="btn btn--primary" @click="createNewTask">
        <AppIcon name="plus" :size="16" />
        新建 Task
      </button>
    </EmptyState>

    <EmptyState
      v-else-if="visibleTasks.length === 0"
      icon="search"
      title="没有匹配的 Task"
      description="尝试清空搜索或切换状态筛选。"
    >
      <button type="button" class="btn btn--ghost" @click="clearFilters">
        清空筛选
      </button>
    </EmptyState>

    <div v-else class="task-groups">
      <section v-if="globalTasks.length" class="task-group">
        <header class="task-group__head">
          <button
            type="button"
            class="task-group__toggle"
            :aria-expanded="isExpanded('global')"
            @click="toggleGroup('global')"
          >
            <AppIcon
              name="chevron-down"
              :size="14"
              class="task-group__chevron"
              :class="{ 'task-group__chevron--open': isExpanded('global') }"
            />
            <span>
              <h2 class="task-group__title">Global Workspace</h2>
              <span class="task-group__desc">未绑定 Project 的临时任务</span>
            </span>
          </button>
          <span class="task-group__count">{{ globalTasks.length }}</span>
        </header>
        <ul v-if="isExpanded('global')" class="task-list">
          <li v-for="task in globalTasks" :key="task.id" class="task-list__item">
            <button
              type="button"
              class="task-row"
              @click="router.push({ name: 'task', params: { id: task.id } })"
            >
              <span class="task-row__icon"><AppIcon name="flag" :size="15" /></span>
              <span class="task-row__main">
                <span class="task-row__title">{{ task.title }}</span>
                <span class="task-row__meta">
                  Global Workspace · {{ modelLabel(task) }} · 更新于
                  {{ formatRelative(task.updated_at) }}
                </span>
              </span>
              <StatusBadge :status="task.status" kind="task" />
              <AppIcon name="chevron-right" :size="14" class="task-row__chevron" />
            </button>
            <EntityMenu
              kind="task"
              :name="task.title"
              :archived="task.status === 'archived'"
              @rename="(title) => renameTask(task, title)"
              @toggle-archive="toggleArchive(task)"
              @remove="removeTask(task)"
            />
          </li>
        </ul>
      </section>

      <section
        v-for="group in projectGroups"
        :key="group.projectId"
        class="task-group"
      >
        <header class="task-group__head">
          <button
            type="button"
            class="task-group__toggle"
            :aria-expanded="isExpanded(group.projectId)"
            @click="toggleGroup(group.projectId)"
          >
            <AppIcon
              name="chevron-down"
              :size="14"
              class="task-group__chevron"
              :class="{ 'task-group__chevron--open': isExpanded(group.projectId) }"
            />
            <h2 class="task-group__title">{{ group.projectName }}</h2>
          </button>
          <div class="task-group__actions">
            <span class="task-group__count">{{ group.tasks.length }}</span>
            <div class="task-group__menu-wrap">
              <button
                type="button"
                class="task-group__menu-trigger"
                :aria-expanded="openGroupMenu === group.projectId"
                aria-label="Project 操作"
                @click.stop="toggleGroupMenu(group.projectId)"
              >
                <AppIcon name="more" :size="16" />
              </button>

              <div
                v-if="openGroupMenu === group.projectId"
                class="task-group__menu-backdrop"
                @click="openGroupMenu = null"
              />
              <div
                v-if="openGroupMenu === group.projectId"
                class="task-group__menu"
                @click.stop
              >
                <button
                  type="button"
                  class="task-group__menu-item"
                  @click="toggleProjectPin(group.projectId)"
                >
                  <AppIcon name="pin" :size="14" />
                  {{ isProjectPinned(group.projectId) ? '取消置顶' : '置顶' }}
                </button>
                <button
                  type="button"
                  class="task-group__menu-item"
                  @click="viewGroupProject(group.projectId)"
                >
                  <AppIcon name="chevron-right" :size="14" />
                  查看详情
                </button>
                <button
                  type="button"
                  class="task-group__menu-item task-group__menu-item--danger"
                  @click="requestDeleteProject(group)"
                >
                  <AppIcon name="trash" :size="14" />
                  删除 Project
                </button>
              </div>
            </div>
          </div>
        </header>
        <ul v-if="isExpanded(group.projectId)" class="task-list">
          <li v-for="task in group.tasks" :key="task.id" class="task-list__item">
            <button
              type="button"
              class="task-row"
              @click="router.push({ name: 'task', params: { id: task.id } })"
            >
              <span class="task-row__icon"><AppIcon name="flag" :size="15" /></span>
              <span class="task-row__main">
                <span class="task-row__title">{{ task.title }}</span>
                <span class="task-row__meta">
                  {{ group.projectName }} · {{ modelLabel(task) }} · 更新于
                  {{ formatRelative(task.updated_at) }}
                </span>
              </span>
              <StatusBadge :status="task.status" kind="task" />
              <AppIcon name="chevron-right" :size="14" class="task-row__chevron" />
            </button>
            <EntityMenu
              kind="task"
              :name="task.title"
              :archived="task.status === 'archived'"
              @rename="(title) => renameTask(task, title)"
              @toggle-archive="toggleArchive(task)"
              @remove="removeTask(task)"
            />
          </li>
        </ul>
      </section>
    </div>

    <ConfirmDialog
      :open="Boolean(deleteProjectTarget)"
      title="删除 Project"
      :message="'确定删除「' + (deleteProjectTarget?.name ?? '') + '」吗？\n\n若 Project 中仍有 Task 或文件引用，后端会拒绝删除。'"
      confirm-label="删除"
      danger
      :busy="deletingProject"
      @confirm="confirmDeleteProject"
      @close="deleteProjectTarget = null"
    />
  </div>
</template>

<style scoped>
.tasks-view {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.tasks-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  width: min(420px, 100%);
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-muted);
}

.search-box:focus-within {
  border-color: var(--accent-border);
}

.search-box__input {
  flex: 1;
  height: 40px;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 13.5px;
  outline: none;
}

.filter-wrap {
  position: relative;
}

.filter-trigger {
  position: relative;
  z-index: 60;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}

.filter-trigger:hover,
.filter-trigger--active {
  border-color: var(--accent-border);
  color: var(--text);
}

.filter-trigger__badge {
  display: grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--accent);
  color: #1b120d;
  font-family: var(--font-mono);
  font-size: 12px;
}

.filter-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
}

.filter-popover {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 50;
  width: 280px;
  padding: 16px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  background: var(--bg-raised);
  box-shadow: var(--shadow-lg);
}

.filter-section + .filter-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.filter-section__title {
  margin: 0 0 10px;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.filter-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}

.filter-option input {
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
}

.filter-clear {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  margin-top: 16px;
  padding: 10px 0 2px;
  border: 0;
  border-top: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
}

.filter-clear:hover {
  color: var(--text);
}

.toolbar__count {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.03em;
  color: var(--text-muted);
}

.task-groups {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.task-group__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 2px 10px;
  border-bottom: 1px solid var(--border);
}

.task-group__toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.task-group__chevron {
  flex-shrink: 0;
  color: var(--text-muted);
  transform: rotate(-90deg);
  transition: transform 0.16s ease;
}

.task-group__chevron--open {
  transform: rotate(0deg);
}

.task-group__title {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: var(--font-size-section);
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--text);
}

.task-group__desc {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
}

.task-group__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.task-group__menu-wrap {
  position: relative;
}

.task-group__menu-trigger {
  position: relative;
  z-index: 60;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.task-group__menu-trigger:hover {
  border-color: var(--border);
  background: var(--bg-subtle);
  color: var(--text);
}

.task-group__menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
}

.task-group__menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 50;
  width: 190px;
  padding: 6px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  background: var(--bg-raised);
  box-shadow: var(--shadow-lg);
}

.task-group__menu-item {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 9px 10px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.task-group__menu-item:hover {
  background: var(--bg-subtle);
  color: var(--text);
}

.task-group__menu-item--danger {
  color: var(--danger);
}

.task-group__menu-item--danger:hover {
  background: var(--danger-soft);
  color: var(--danger);
}

.task-group__count {
  font-family: var(--font-display);
  font-size: 15px;
  color: var(--text-muted);
}

.task-group__link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

.task-group__link:hover {
  color: var(--accent);
}

.task-list {
  list-style: none;
  margin: 0;
  padding: 0;
  border-top: 0;
}

.task-list__item {
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid var(--border);
}

.task-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
  padding: 15px 4px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.task-row:hover {
  background: var(--bg-subtle);
}

.task-row__icon {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  color: var(--accent);
}

.task-row__main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
  min-width: 0;
}

.task-row__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  color: var(--text);
}

.task-row__meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--text-muted);
}

.task-row__chevron {
  flex-shrink: 0;
  color: var(--text-muted);
}

@media (max-width: 720px) {
  .toolbar__count {
    margin-left: 0;
  }
}
</style>
