<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import TaskArtifacts from '@/components/TaskArtifacts.vue'
import EntityMenu from '@/components/EntityMenu.vue'
import FilePickerModal from '@/components/FilePickerModal.vue'
import FilePreviewModal from '@/components/FilePreviewModal.vue'
import LoadingState from '@/components/LoadingState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  deleteTask,
  getProject,
  getTask,
  getTaskFiles,
  listModels,
  listProjects,
  listTasks,
  removeTaskFileOverride,
  updateTask,
  updateTaskFile,
} from '@/api/endpoints'
import type {
  FileItem,
  ModelInfo,
  Project,
  Task,
  TaskAvailableFile,
  TaskFileContext,
  TaskStatus,
  TaskUsage,
} from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage, isNotFound } from '@/utils/errors'
import {
  fileTypeLabel,
  formatBytes,
  formatDateTime,
  formatRelative,
  taskStatusLabel,
} from '@/utils/format'

type TabKey = 'chat' | 'settings' | 'artifacts'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const taskId = computed(() => String(route.params.id ?? ''))

const task = ref<Task | null>(null)
const project = ref<Project | null>(null)
const fileContext = ref<TaskFileContext | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const notFound = ref(false)

const activeTab = ref<TabKey>('chat')
const highlightMessageId = ref<string | null>(null)
const statusDraft = ref<string>('active')
const statusUpdating = ref(false)

const pickerOpen = ref(false)
const previewFile = ref<FileItem | null>(null)
const fileActionBusy = ref<string | null>(null)
const addingFiles = ref(false)

const models = ref<ModelInfo[]>([])
const navTasks = ref<Task[]>([])
const navProjects = ref<Project[]>([])
const modelSaving = ref(false)
const selectedModel = ref('')

const temperatureDraft = ref('')
const maxTokensDraft = ref('')
const paramsSaving = ref(false)

const statusOptions: { value: TaskStatus; label: string }[] = [
  { value: 'active', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'archived', label: '已归档' },
]

const navGlobalTasks = computed(() =>
  navTasks.value.filter((item) => !item.project_id),
)

const navProjectGroups = computed(() => {
  const groups = new Map<string, Task[]>()
  for (const item of navTasks.value) {
    if (!item.project_id) continue
    const list = groups.get(item.project_id) ?? []
    list.push(item)
    groups.set(item.project_id, list)
  }
  const names = new Map(navProjects.value.map((item) => [item.id, item.name]))
  return Array.from(groups.entries())
    .map(([projectId, items]) => ({
      projectId,
      projectName: names.get(projectId) ?? '关联 Project',
      tasks: items,
    }))
    .sort((a, b) => a.projectName.localeCompare(b.projectName, 'zh-CN'))
})

const tabs = computed(() => [
  { key: 'chat' as TabKey, label: 'Chat' },
  { key: 'settings' as TabKey, label: 'Settings' },
  { key: 'artifacts' as TabKey, label: 'Artifacts' },
])

// Backend may label inherited files "project_inherited" (current contract) or
// the shorter "project"; treat both as project-inherited so the UI never
// misclassifies a file.
function isInherited(item: TaskAvailableFile): boolean {
  return item.source === 'project' || item.source === 'project_inherited'
}

const projectFiles = computed<TaskAvailableFile[]>(
  () => (fileContext.value?.available ?? []).filter(isInherited),
)

const extraFiles = computed<TaskAvailableFile[]>(
  () => (fileContext.value?.available ?? []).filter((item) => !isInherited(item)),
)

const excludedFiles = computed<FileItem[]>(() => fileContext.value?.excluded ?? [])

const totalAvailable = computed(() => fileContext.value?.available.length ?? 0)

const pickerExcludedIds = computed<string[]>(() => [
  ...(fileContext.value?.available ?? []).map((item) => item.file.id),
  ...(fileContext.value?.excluded ?? []).map((file) => file.id),
])

type FileRowSource = 'project_inherited' | 'task_added' | 'excluded'
type FileFilter = 'all' | FileRowSource

interface FileRow {
  file: FileItem
  source: FileRowSource
}

const fileFilter = ref<FileFilter>('all')
const fileRows = computed<FileRow[]>(() => [
  ...projectFiles.value.map((item) => ({ file: item.file, source: 'project_inherited' as const })),
  ...extraFiles.value.map((item) => ({ file: item.file, source: 'task_added' as const })),
  ...excludedFiles.value.map((file) => ({ file, source: 'excluded' as const })),
])
const visibleFileRows = computed<FileRow[]>(() =>
  fileFilter.value === 'all'
    ? fileRows.value
    : fileRows.value.filter((row) => row.source === fileFilter.value),
)

function sourceLabel(source: FileRowSource): string {
  if (source === 'project_inherited') return '项目继承'
  if (source === 'task_added') return '额外引用'
  return '已排除'
}

async function handleFileAction(row: FileRow): Promise<void> {
  if (row.source === 'excluded') {
    await restoreFile(row.file)
    return
  }
  if (row.source === 'task_added') {
    await removeExtraFile(row.file)
    return
  }
  const item = projectFiles.value.find((entry) => entry.file.id === row.file.id)
  if (item) await excludeFile(item)
}

const modelLabel = computed(() => {
  const current = task.value
  if (!current || !current.model_name) return '未配置模型'
  return current.model_provider ? `${current.model_provider} / ${current.model_name}` : current.model_name
})

const fileContextError = ref<string | null>(null)

async function loadFileContext(): Promise<void> {
  const id = taskId.value
  if (!id) return
  fileContextError.value = null
  try {
    fileContext.value = await getTaskFiles(id)
  } catch (error) {
    fileContextError.value = errorMessage(error)
    fileContext.value = null
  }
}

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  notFound.value = false
  fileContext.value = null
  project.value = null
  const id = taskId.value
  if (!id) {
    notFound.value = true
    loading.value = false
    return
  }
  try {
    const current = await getTask(id)
    task.value = current
    statusDraft.value = current.status
    syncSelectedModel()
    syncModelParams()
    const projectPromise = current.project_id
      ? getProject(current.project_id).catch(() => null)
      : Promise.resolve(null)
    const [projectResult] = await Promise.all([projectPromise, loadFileContext()])
    project.value = projectResult
  } catch (error) {
    if (isNotFound(error)) {
      notFound.value = true
    } else {
      loadError.value = errorMessage(error)
    }
  } finally {
    loading.value = false
  }
}

async function changeStatus(): Promise<void> {
  const current = task.value
  if (!current || statusDraft.value === current.status) return
  const previous = current.status
  statusUpdating.value = true
  try {
    task.value = await updateTask(current.id, { status: statusDraft.value as TaskStatus })
    statusDraft.value = task.value.status
    app.notify('success', `任务状态已更新为「${taskStatusLabel(task.value.status)}」`)
  } catch (error) {
    statusDraft.value = previous
    app.notifyError(error)
  } finally {
    statusUpdating.value = false
  }
}

async function excludeFile(item: TaskAvailableFile): Promise<void> {
  fileActionBusy.value = item.file.id
  try {
    await updateTaskFile(taskId.value, { file_id: item.file.id, action: 'exclude' })
    app.notify('success', `已排除「${item.file.filename}」`)
    await loadFileContext()
  } catch (error) {
    app.notifyError(error)
  } finally {
    fileActionBusy.value = null
  }
}

async function removeOverride(file: FileItem, message: string): Promise<void> {
  fileActionBusy.value = file.id
  try {
    await removeTaskFileOverride(taskId.value, file.id)
    app.notify('success', message)
    await loadFileContext()
  } catch (error) {
    app.notifyError(error)
  } finally {
    fileActionBusy.value = null
  }
}

async function restoreFile(file: FileItem): Promise<void> {
  await removeOverride(file, `已恢复「${file.filename}」`)
}

async function removeExtraFile(file: FileItem): Promise<void> {
  await removeOverride(file, `已移除额外引用「${file.filename}」`)
}

async function addExtraFiles(selected: FileItem[]): Promise<void> {
  if (selected.length === 0) return
  addingFiles.value = true
  let added = 0
  const failures: string[] = []
  for (const file of selected) {
    try {
      await updateTaskFile(taskId.value, { file_id: file.id, action: 'include' })
      added += 1
    } catch (error) {
      failures.push(`${file.filename}：${errorMessage(error)}`)
    }
  }
  pickerOpen.value = false
  addingFiles.value = false
  if (added > 0) {
    app.notify('success', `已添加 ${added} 个额外引用文件`)
    await loadFileContext()
  }
  for (const failure of failures) {
    app.notify('error', failure)
  }
}

const allProjects = ref<Project[]>([])
const bindingProjectId = ref('')
const binding = ref(false)

async function loadNavigation(): Promise<void> {
  try {
    const [taskList, projectList] = await Promise.all([
      listTasks({ limit: 200 }),
      listProjects({ limit: 200 }),
    ])
    navTasks.value = taskList
    navProjects.value = projectList
  } catch {
    navTasks.value = []
    navProjects.value = []
  }
}

async function loadProjects(): Promise<void> {
  try {
    const list = await listProjects({ limit: 200 })
    allProjects.value = list.filter((item) => item.status === 'active')
  } catch {
    allProjects.value = []
  }
}

async function renameTask(name: string): Promise<void> {
  const current = task.value
  if (!current) return
  try {
    task.value = await updateTask(current.id, { title: name })
    app.notify('success', '任务已重命名')
  } catch (error) {
    app.notifyError(error)
  }
}

async function toggleTaskArchive(): Promise<void> {
  const current = task.value
  if (!current) return
  const next: TaskStatus = current.status === 'archived' ? 'active' : 'archived'
  try {
    task.value = await updateTask(current.id, { status: next })
    statusDraft.value = task.value.status
    app.notify('success', next === 'archived' ? '任务已归档' : '任务已取消归档')
  } catch (error) {
    app.notifyError(error)
  }
}

async function removeTask(): Promise<void> {
  const current = task.value
  if (!current) return
  try {
    await deleteTask(current.id)
    app.notify('success', '任务已删除')
    if (project.value) void router.replace(`/projects/${project.value.id}`)
    else void router.replace('/')
  } catch (error) {
    app.notifyError(error)
  }
}

async function bindProject(): Promise<void> {
  const current = task.value
  if (!current || !bindingProjectId.value) return
  binding.value = true
  try {
    task.value = await updateTask(current.id, { project_id: bindingProjectId.value })
    await load()
    app.notify('success', '已绑定 Project（后续不可更改）')
  } catch (error) {
    app.notifyError(error)
  } finally {
    binding.value = false
  }
}

function modelKey(provider: string, model: string): string {
  return `${provider}::${model}`
}

function syncSelectedModel(): void {
  const current = task.value
  if (current?.model_provider && current.model_name) {
    selectedModel.value = modelKey(current.model_provider, current.model_name)
  } else {
    selectedModel.value = ''
  }
}

async function loadModels(): Promise<void> {
  try {
    models.value = await listModels()
  } catch {
    models.value = []
  }
  syncSelectedModel()
}

async function changeModel(): Promise<void> {
  const current = task.value
  if (!current || !selectedModel.value) return
  const [provider, model] = selectedModel.value.split('::')
  modelSaving.value = true
  try {
    task.value = await updateTask(current.id, {
      model_provider: provider,
      model_name: model,
    })
    app.notify('success', `模型已切换为 ${provider} / ${model}`)
  } catch (error) {
    app.notifyError(error)
    syncSelectedModel()
  } finally {
    modelSaving.value = false
  }
}

function syncModelParams(): void {
  const current = task.value
  temperatureDraft.value = current?.temperature != null ? String(current.temperature) : ''
  maxTokensDraft.value = current?.max_tokens != null ? String(current.max_tokens) : ''
}

async function saveModelParams(): Promise<void> {
  const current = task.value
  if (!current) return
  const temperature = temperatureDraft.value.trim() === '' ? null : Number(temperatureDraft.value)
  const maxTokens = maxTokensDraft.value.trim() === '' ? null : Number(maxTokensDraft.value)
  if (temperature !== null && (Number.isNaN(temperature) || temperature < 0 || temperature > 2)) {
    app.notify('error', 'Temperature 需在 0 到 2 之间')
    return
  }
  if (maxTokens !== null && (!Number.isInteger(maxTokens) || maxTokens < 1 || maxTokens > 32000)) {
    app.notify('error', 'Max tokens 需为 1 到 32000 的整数')
    return
  }
  paramsSaving.value = true
  try {
    task.value = await updateTask(current.id, {
      temperature,
      max_tokens: maxTokens,
    })
    syncModelParams()
    app.notify('success', '模型参数已保存')
  } catch (error) {
    app.notifyError(error)
  } finally {
    paramsSaving.value = false
  }
}

function onUsageUpdated(usage: TaskUsage | null): void {
  if (task.value) task.value = { ...task.value, usage }
}

async function openSourceMessage(messageId: string): Promise<void> {
  activeTab.value = 'chat'
  highlightMessageId.value = null
  await nextTick()
  highlightMessageId.value = messageId
}

watch(taskId, () => {
  activeTab.value = 'chat'
  void load()
  void loadNavigation()
})

onMounted(() => {
  if (route.query.tab === 'artifacts') activeTab.value = 'artifacts'
  void load()
  void loadProjects()
  void loadNavigation()
  void loadModels()
})
</script>

<template>
  <div class="task-view">
    <LoadingState v-if="loading" label="正在加载任务…" />

    <div v-else-if="notFound" class="state-page">
      <EmptyState icon="sparkles" title="Task 不存在" description="该任务可能已被删除，或链接无效。">
        <RouterLink to="/" class="btn btn--ghost">返回 Home</RouterLink>
      </EmptyState>
    </div>

    <div v-else-if="loadError" class="panel panel--error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">任务加载失败</p>
        <p class="panel--error__desc">{{ loadError }}</p>
      </div>
      <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
    </div>

    <template v-else-if="task">
      <div class="task-layout">
        <aside class="task-nav" aria-label="Task 快速切换">
          <div class="task-nav__top">
            <span class="task-nav__eyebrow">WORKSPACE</span>
            <RouterLink to="/tasks" class="task-nav__all">All Tasks</RouterLink>
          </div>

          <details
            v-for="group in navProjectGroups"
            :key="group.projectId"
            class="task-nav__group"
            :open="group.projectId === task.project_id"
          >
            <summary class="task-nav__project">
              <span class="task-nav__project-name">{{ group.projectName }}</span>
              <span class="task-nav__count">{{ group.tasks.length }}</span>
            </summary>
            <RouterLink
              v-for="item in group.tasks"
              :key="item.id"
              :to="'/tasks/' + item.id"
              class="task-nav__item"
              :class="{ 'task-nav__item--active': item.id === task.id }"
            >
              <span class="task-nav__flag" :class="'task-nav__flag--' + item.status"><AppIcon name="flag" :size="12" /></span>
              <span class="task-nav__title">{{ item.title }}</span>
              <span class="task-nav__time">
                {{ item.last_message_at ? formatRelative(item.last_message_at) : '—' }}
              </span>
            </RouterLink>
          </details>

          <details
            v-if="navGlobalTasks.length"
            class="task-nav__group"
            :open="!task.project_id"
          >
            <summary class="task-nav__project">
              <span class="task-nav__project-name">Global Workspace</span>
              <span class="task-nav__count">{{ navGlobalTasks.length }}</span>
            </summary>
            <RouterLink
              v-for="item in navGlobalTasks"
              :key="item.id"
              :to="'/tasks/' + item.id"
              class="task-nav__item"
              :class="{ 'task-nav__item--active': item.id === task.id }"
            >
              <span class="task-nav__flag" :class="'task-nav__flag--' + item.status"><AppIcon name="flag" :size="12" /></span>
              <span class="task-nav__title">{{ item.title }}</span>
              <span class="task-nav__time">
                {{ item.last_message_at ? formatRelative(item.last_message_at) : '—' }}
              </span>
            </RouterLink>
          </details>
        </aside>

        <div class="task-main">
      <header class="task-head">
        <div class="task-head__main">
          <nav class="crumbs" aria-label="面包屑">
            <RouterLink to="/" class="crumb">Home</RouterLink>
            <span class="crumb-sep" aria-hidden="true">/</span>
            <RouterLink v-if="project" :to="`/projects/${project.id}`" class="crumb">
              {{ project.name }}
            </RouterLink>
            <span v-else class="crumb crumb--muted">Global Workspace</span>
            <span class="crumb-sep" aria-hidden="true">/</span>
            <span class="crumb crumb--current">Task</span>
          </nav>
          <div class="task-head__title-row">
            <h1 class="task-head__title">{{ task.title }}</h1>
            <StatusBadge :status="task.status" kind="task" />
          </div>
          <p v-if="task.description" class="task-head__desc">{{ task.description }}</p>
          <div class="task-head__meta">
            <span class="meta-item">
              <AppIcon name="folder" :size="13" />
              <template v-if="project">{{ project.name }}</template>
              <template v-else>不属于任何 Project</template>
            </span>
            <span class="meta-item">
              <AppIcon name="sparkles" :size="13" />
              {{ modelLabel }}
            </span>
            <span class="meta-item">
              <AppIcon name="clock" :size="13" />
              创建于 {{ formatDateTime(task.created_at) }}
            </span>
          </div>
        </div>
        <div class="task-head__actions">
          <span v-if="statusUpdating" class="spinner spinner--sm" aria-hidden="true" />
          <label class="status-select">
            <span class="status-select__label">任务状态</span>
            <select
              v-model="statusDraft"
              class="select select--compact"
              :disabled="statusUpdating"
              aria-label="修改任务状态"
              @change="changeStatus"
            >
              <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
          <EntityMenu
            :name="task.title"
            kind="task"
            :archived="task.status === 'archived'"
            @rename="renameTask"
            @toggle-archive="toggleTaskArchive"
            @remove="removeTask"
          />
        </div>
      </header>

      <div class="tabbar" role="tablist" aria-label="任务分区">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          role="tab"
          class="tab"
          :class="{ 'tab--active': activeTab === tab.key }"
          :aria-selected="activeTab === tab.key"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Chat -->
      <section v-show="activeTab === 'chat'" role="tabpanel" class="tab-panel chat-panel">
        <div class="card chat-card">
          <ChatPanel
            :task-id="task.id"
            :has-model="models.length > 0"
            :task="task"
            :models="models"
            @usage-updated="onUsageUpdated"
            @task-updated="task = $event"
            @open-artifacts="activeTab = 'artifacts'"
            :highlight-message-id="highlightMessageId"
          />
        </div>
      </section>

      <!-- Settings -->
      <section v-if="activeTab === 'settings'" role="tabpanel" class="tab-panel">
        <section class="card project-binding">
          <header class="project-binding__head">
            <h2 class="context-title">所属 Project</h2>
          </header>
          <template v-if="task.project_id">
            <p class="project-binding__value">
              当前绑定：<strong>{{ project?.name ?? task.project_id }}</strong>
            </p>
            <p class="project-binding__hint">已绑定，不可更改或解除。</p>
          </template>
          <template v-else>
            <div class="project-binding__row">
              <select v-model="bindingProjectId" class="select" :disabled="binding">
                <option value="">选择要绑定的 Project…</option>
                <option v-for="item in allProjects" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
              <button
                type="button"
                class="btn btn--primary btn--sm"
                :disabled="binding || !bindingProjectId"
                @click="bindProject"
              >
                <span v-if="binding" class="spinner spinner--sm" aria-hidden="true" />
                绑定
              </button>
            </div>
            <p class="project-binding__hint">
              绑定后该 Task 会继承该项目文件作为可用上下文，且绑定后不可更改。
            </p>
          </template>
        </section>

        <div v-if="fileContextError" class="panel panel--error">
          <AppIcon name="alert" :size="16" />
          <div>
            <p class="panel--error__title">文件上下文加载失败</p>
            <p class="panel--error__desc">{{ fileContextError }}</p>
          </div>
          <button type="button" class="btn btn--ghost btn--sm" @click="loadFileContext">重试</button>
        </div>

        <template v-else>
          <section class="card context-section">
            <header class="context-head">
              <div>
                <h2 class="context-title">文件上下文</h2>
                <p class="context-desc">
                  项目继承 + 额外引用 − 排除 = 可用文件；这里管理的是可用上下文，不是实际读取的文件。
                </p>
              </div>
              <button
                type="button"
                class="btn btn--ghost btn--sm"
                :disabled="addingFiles"
                @click="pickerOpen = true"
              >
                <AppIcon name="plus" :size="14" />
                从 Library 添加
              </button>
            </header>

            <div class="file-tabs" role="tablist" aria-label="文件上下文分类">
              <button
                type="button"
                class="file-tab"
                :class="{ 'file-tab--active': fileFilter === 'all' }"
                @click="fileFilter = 'all'"
              >
                全部
                <span class="chip chip--muted">{{ totalAvailable + excludedFiles.length }}</span>
              </button>
              <button
                type="button"
                class="file-tab"
                :class="{ 'file-tab--active': fileFilter === 'project_inherited' }"
                @click="fileFilter = 'project_inherited'"
              >
                项目继承
                <span class="chip chip--muted">{{ projectFiles.length }}</span>
              </button>
              <button
                type="button"
                class="file-tab"
                :class="{ 'file-tab--active': fileFilter === 'task_added' }"
                @click="fileFilter = 'task_added'"
              >
                额外引用
                <span class="chip chip--muted">{{ extraFiles.length }}</span>
              </button>
              <button
                type="button"
                class="file-tab"
                :class="{ 'file-tab--active': fileFilter === 'excluded' }"
                @click="fileFilter = 'excluded'"
              >
                已排除
                <span class="chip chip--muted">{{ excludedFiles.length }}</span>
              </button>
            </div>

            <div v-if="!project && fileFilter === 'project_inherited'" class="context-empty">
              该 Task 不属于任何 Project，因此没有项目继承文件。
            </div>
            <div v-else-if="visibleFileRows.length === 0" class="context-empty">
              当前分类下没有文件。
            </div>
            <ul v-else class="file-list">
              <li
                v-for="row in visibleFileRows"
                :key="row.file.id"
                class="file-item"
                :class="{ 'file-item--muted': row.source === 'excluded' }"
              >
                <span class="file-item__icon"><AppIcon name="file" :size="15" /></span>
                <button
                  type="button"
                  class="file-item__main file-item__main--button"
                  @click="previewFile = row.file"
                >
                  <span class="file-item__name" :title="row.file.filename">{{ row.file.filename }}</span>
                  <span class="file-item__meta">
                    {{ fileTypeLabel(row.file.file_type) }} · {{ formatBytes(row.file.size) }}
                  </span>
                </button>
                <span class="file-item__source" :class="'file-item__source--' + row.source">
                  {{ sourceLabel(row.source) }}
                </span>
                <button
                  type="button"
                  class="btn btn--ghost btn--sm"
                  :disabled="fileActionBusy === row.file.id"
                  @click="handleFileAction(row)"
                >
                  <span v-if="fileActionBusy === row.file.id" class="spinner spinner--sm" aria-hidden="true" />
                  {{ row.source === 'excluded' ? '恢复' : row.source === 'task_added' ? '移除' : '排除' }}
                </button>
              </li>
            </ul>
          </section>

        </template>
      </section>

      <!-- Artifacts -->
      <section v-if="activeTab === 'artifacts'" role="tabpanel" class="tab-panel">
        <TaskArtifacts
          :task-id="task.id"
          @open-source-message="openSourceMessage"
        />
      </section>

      <FilePreviewModal
        :file-id="previewFile?.id ?? null"
        @close="previewFile = null"
      />

      <FilePickerModal
        :open="pickerOpen"
        :exclude-ids="pickerExcludedIds"
        title="添加额外引用文件"
        description="从 Global Library 选择文件加入当前 Task 的可用上下文，不依赖 Project 继承关系。"
        confirm-label="添加引用"
        @close="pickerOpen = false"
        @selected="addExtraFiles"
      />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.task-view {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.task-layout {
  display: grid;
  grid-template-columns: 218px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.task-main {
  min-width: 0;
  width: 100%;
  max-width: 940px;
}

.task-nav {
  position: sticky;
  top: calc(var(--topbar-height) + 20px);
  max-height: calc(100vh - var(--topbar-height) - 44px);
  overflow-y: auto;
  padding: 0 12px 18px 0;
  border-right: 1px solid var(--border);
}

.task-nav__top {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.task-nav__eyebrow {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  color: var(--text-muted);
}

.task-nav__all {
  font-family: var(--font-display);
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--text);
}

.task-nav__all:hover {
  color: var(--accent);
}

.task-nav__group {
  margin-top: 16px;
}

.task-nav__heading {
  margin: 0 0 6px;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.task-nav__project {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 2px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  list-style: none;
}

.task-nav__project::-webkit-details-marker {
  display: none;
}

.task-nav__project:hover {
  color: var(--text);
}

.task-nav__project-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-nav__count {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

.task-nav__item {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 8px;
  margin-left: 8px;
  border-left: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.4;
}

.task-nav__flag {
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.task-nav__flag--active {
  color: var(--accent);
}

.task-nav__flag--completed {
  color: var(--success);
}

.task-nav__flag--archived {
  color: var(--text-faint);
}

.task-nav__title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-nav__time {
  flex-shrink: 0;
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.task-nav__item:hover {
  color: var(--text);
  border-left-color: var(--border-strong);
}

.task-nav__item--active {
  color: var(--accent);
  border-left-color: var(--accent);
  background: var(--accent-soft);
}

@media (max-width: 1000px) {
  .task-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .task-nav {
    display: none;
  }

  .task-main {
    max-width: none;
  }
}

.state-page {
  padding-top: 24px;
}

.task-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border);
}

.task-head__main {
  min-width: 0;
}

.crumbs {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  font-family: var(--font-mono);
  font-size: 12.5px;
  letter-spacing: 0.03em;
}

.crumb {
  color: var(--text-muted);
  transition: color 0.14s ease;
}

.crumb:hover {
  color: var(--text);
}

.crumb--muted {
  color: var(--text-faint);
}

.crumb--current {
  color: var(--text-secondary);
}

.crumb-sep {
  color: var(--text-faint);
}

.task-head__title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.task-head__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 38px;
  font-weight: 600;
  letter-spacing: -0.035em;
  line-height: 1.15;
  overflow-wrap: anywhere;
}

.task-head__desc {
  margin: 8px 0 0;
  max-width: 720px;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-secondary);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.task-head__meta {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--text-muted);
}

.task-head__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  padding-top: 22px;
}

.status-select {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-select__label {
  font-size: 12px;
  color: var(--text-faint);
}

.tabbar {
  display: flex;
  align-items: center;
  gap: 28px;
  border-bottom: 1px solid var(--border);
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 11px 0;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  cursor: pointer;
  transition: color 0.14s ease;
}

.tab:hover {
  color: var(--text);
}

.tab--active {
  color: var(--text);
  border-bottom-color: var(--accent);
}

.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-top: 10px;
}

.chat-panel {
  min-height: 420px;
}

.chat-layout {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.chat-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: sticky;
  top: 16px;
}

.chat-main {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

@media (max-width: 1100px) {
  .chat-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .chat-sidebar {
    position: static;
    flex-direction: row;
    flex-wrap: wrap;
  }
}

.chat-card {
  display: flex;
  flex-direction: column;
  min-height: 420px;
  padding: 0;
  overflow: hidden;
}

.chat-card :deep(.empty-state) {
  flex: 1;
}

.composer {
  padding: 0 18px 18px;
}

.composer__box {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-raised);
  box-shadow: inset 0 1px 0 var(--border-strong);
  overflow: hidden;
}

.composer__input {
  display: block;
  width: 100%;
  padding: 12px 14px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font: inherit;
  font-size: 13px;
  line-height: 1.6;
  resize: none;
  outline: none;
  cursor: not-allowed;
}

.composer__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px 8px 14px;
  border-top: 1px solid var(--border);
}

.composer__hint {
  font-size: 12px;
  color: var(--text-faint);
}

.notice {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 11px 14px;
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 1.6;
}

.notice :deep(svg) {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--accent);
}

.context-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.context-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
}

.context-stat__value {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.1;
}

.context-stat__label {
  font-size: 12px;
  color: var(--text-faint);
}

.context-section {
  padding: 0;
  overflow: hidden;
}

.context-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.context-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--font-size-section);
  font-weight: 600;
  letter-spacing: -0.015em;
  color: var(--text);
}

.context-desc {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-muted);
}

.context-empty {
  padding: 16px;
  font-size: 12.5px;
  color: var(--text-muted);
  line-height: 1.6;
}

.context-link {
  margin-left: 6px;
  color: var(--accent);
}

.context-link:hover {
  text-decoration: underline;
}

.file-list {
  list-style: none;
  margin: 0;
  padding: 4px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  transition: background 0.13s ease;
}

.file-item:hover {
  background: var(--bg-hover);
}

.file-item--muted {
  opacity: 0.82;
}

.file-item__icon {
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

.file-item__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.file-item__main--button {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.file-item__main--button:hover .file-item__name {
  color: var(--accent);
}

.file-item__name {
  font-size: 13px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-item__meta {
  font-size: 12px;
  color: var(--text-faint);
}

.model-info {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
  padding: 16px;
}

.model-info__label {
  font-size: 12px;
  color: var(--text-faint);
}

.model-info__value {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-secondary);
}

.model-info__hint {
  font-size: 12px;
  color: var(--text-faint);
}

.project-binding {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.project-binding__head {
  margin: 0;
}

.project-binding__row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.project-binding__value {
  margin: 0;
  color: var(--text-secondary);
}

.project-binding__hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.model-select {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
}

.model-select__hint {
  font-size: 12px;
  color: var(--text-muted);
}

.model-params {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 0 16px 12px;
  flex-wrap: wrap;
}

.model-params .field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 130px;
}

.model-params .field__label {
  font-size: 12px;
  color: var(--text-muted);
}

.file-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 16px 12px;
}

.file-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition:
    border-color 0.13s ease,
    color 0.13s ease,
    background 0.13s ease;
}

.file-tab:hover {
  border-color: var(--border-strong);
  color: var(--text);
}

.file-tab--active {
  border-color: var(--accent-border);
  background: var(--accent-soft);
  color: var(--accent);
}

.file-item__source {
  flex-shrink: 0;
  padding: 1px 7px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 12px;
  color: var(--text-muted);
}

.file-item__source--excluded {
  border-color: var(--danger-soft);
  color: var(--danger);
}

@media (max-width: 900px) {
  .task-head {
    flex-direction: column;
    gap: 12px;
  }

  .task-head__actions {
    padding-top: 0;
  }

  .context-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
