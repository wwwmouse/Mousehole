<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import EmptyState from '@/components/EmptyState.vue'
import EntityMenu from '@/components/EntityMenu.vue'
import FilePickerModal from '@/components/FilePickerModal.vue'
import LoadingState from '@/components/LoadingState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  deleteTask,
  getProject,
  getTask,
  getTaskFiles,
  listProjects,
  removeTaskFileOverride,
  updateTask,
  updateTaskFile,
} from '@/api/endpoints'
import type {
  FileItem,
  Project,
  Task,
  TaskAvailableFile,
  TaskFileContext,
  TaskStatus,
} from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage, isNotFound } from '@/utils/errors'
import {
  fileTypeLabel,
  formatBytes,
  formatDateTime,
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
const statusDraft = ref<string>('active')
const statusUpdating = ref(false)

const pickerOpen = ref(false)
const fileActionBusy = ref<string | null>(null)
const addingFiles = ref(false)

const statusOptions: { value: TaskStatus; label: string }[] = [
  { value: 'active', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'archived', label: '已归档' },
]

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

watch(taskId, () => {
  activeTab.value = 'chat'
  void load()
})

onMounted(() => {
  void load()
  void loadProjects()
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
      <section v-if="activeTab === 'chat'" role="tabpanel" class="tab-panel chat-panel">
        <div class="card chat-card">
          <EmptyState
            icon="sparkles"
            title="对话功能将在 Phase 2 提供"
            description="本阶段先建立 Task、文件上下文与工作空间结构；对话、流式响应与 Execution 状态将随 Phase 2 的模型接入一起开放。"
          />
          <div class="composer">
            <div class="composer__box">
              <textarea
                class="composer__input"
                rows="3"
                placeholder="Chat 输入将在 Phase 2 启用"
                disabled
                aria-label="对话输入框（当前不可用）"
              />
              <div class="composer__bar">
                <span class="composer__hint">当前阶段不发送消息，也不会伪造 AI 回复。</span>
                <button type="button" class="btn btn--primary btn--sm" disabled>
                  <AppIcon name="send" :size="14" />
                  发送
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Settings -->
      <section v-else-if="activeTab === 'settings'" role="tabpanel" class="tab-panel">
        <div class="notice">
          <AppIcon name="info" :size="15" />
          <span>可用文件不等于本次 Execution 实际读取的文件。这里展示的是 Task 的可用上下文，具体执行实际使用了哪些文件以 Execution 详情为准（Phase 2）。</span>
        </div>

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

        <div class="context-stats">
          <div class="context-stat">
            <span class="context-stat__value">{{ totalAvailable }}</span>
            <span class="context-stat__label">可用文件</span>
          </div>
          <div class="context-stat">
            <span class="context-stat__value">{{ projectFiles.length }}</span>
            <span class="context-stat__label">项目继承</span>
          </div>
          <div class="context-stat">
            <span class="context-stat__value">{{ extraFiles.length }}</span>
            <span class="context-stat__label">额外引用</span>
          </div>
          <div class="context-stat">
            <span class="context-stat__value">{{ excludedFiles.length }}</span>
            <span class="context-stat__label">已排除</span>
          </div>
        </div>

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
                <h2 class="context-title">项目继承文件</h2>
                <p class="context-desc">
                  来自所属 Project、默认可用的文件。可以排除不需要的文件。
                </p>
              </div>
              <span class="chip chip--muted">{{ projectFiles.length }}</span>
            </header>
            <div v-if="!project" class="context-empty">
              该 Task 不属于任何 Project，因此没有项目继承文件。
            </div>
            <div v-else-if="projectFiles.length === 0" class="context-empty">
              所属 Project（{{ project.name }}）当前没有关联文件，可先在 Project 的 Files 中添加。
              <RouterLink :to="`/projects/${project.id}`" class="context-link">前往 Project</RouterLink>
            </div>
            <ul v-else class="file-list">
              <li v-for="item in projectFiles" :key="item.file.id" class="file-item">
                <span class="file-item__icon"><AppIcon name="file" :size="15" /></span>
                <div class="file-item__main">
                  <span class="file-item__name" :title="item.file.filename">{{ item.file.filename }}</span>
                  <span class="file-item__meta">
                    {{ fileTypeLabel(item.file.file_type) }} · {{ formatBytes(item.file.size) }} · 来源：项目继承
                  </span>
                </div>
                <button
                  type="button"
                  class="btn btn--ghost btn--sm"
                  :disabled="fileActionBusy === item.file.id"
                  @click="excludeFile(item)"
                >
                  <span v-if="fileActionBusy === item.file.id" class="spinner spinner--sm" aria-hidden="true" />
                  排除
                </button>
              </li>
            </ul>
          </section>

          <section class="card context-section">
            <header class="context-head">
              <div>
                <h2 class="context-title">额外引用文件</h2>
                <p class="context-desc">从 Global Library 手动添加到当前 Task，不依赖 Project 继承关系。</p>
              </div>
              <button type="button" class="btn btn--ghost btn--sm" :disabled="addingFiles" @click="pickerOpen = true">
                <AppIcon name="plus" :size="14" />
                从 Library 添加
              </button>
            </header>
            <div v-if="extraFiles.length === 0" class="context-empty">
              暂无额外引用的文件。可以从 Library 添加与本任务相关的资料。
            </div>
            <ul v-else class="file-list">
              <li v-for="item in extraFiles" :key="item.file.id" class="file-item">
                <span class="file-item__icon"><AppIcon name="file" :size="15" /></span>
                <div class="file-item__main">
                  <span class="file-item__name" :title="item.file.filename">{{ item.file.filename }}</span>
                  <span class="file-item__meta">
                    {{ fileTypeLabel(item.file.file_type) }} · {{ formatBytes(item.file.size) }} · 来源：额外引用
                  </span>
                </div>
                <button
                  type="button"
                  class="btn btn--ghost btn--sm"
                  :disabled="fileActionBusy === item.file.id"
                  @click="removeExtraFile(item.file)"
                >
                  移除
                </button>
              </li>
            </ul>
          </section>

          <section class="card context-section">
            <header class="context-head">
              <div>
                <h2 class="context-title">已排除文件</h2>
                <p class="context-desc">原本来自 Project 继承范围，但被当前 Task 排除的文件。可以恢复使用。</p>
              </div>
              <span class="chip chip--muted">{{ excludedFiles.length }}</span>
            </header>
            <div v-if="excludedFiles.length === 0" class="context-empty">没有被排除的文件。</div>
            <ul v-else class="file-list">
              <li v-for="file in excludedFiles" :key="file.id" class="file-item file-item--muted">
                <span class="file-item__icon"><AppIcon name="file" :size="15" /></span>
                <div class="file-item__main">
                  <span class="file-item__name" :title="file.filename">{{ file.filename }}</span>
                  <span class="file-item__meta">
                    {{ fileTypeLabel(file.file_type) }} · {{ formatBytes(file.size) }} · 状态：已排除
                  </span>
                </div>
                <button
                  type="button"
                  class="btn btn--ghost btn--sm"
                  :disabled="fileActionBusy === file.id"
                  @click="restoreFile(file)"
                >
                  <AppIcon name="refresh" :size="13" />
                  恢复
                </button>
              </li>
            </ul>
          </section>

          <section class="card context-section">
            <header class="context-head">
              <div>
                <h2 class="context-title">模型配置</h2>
                <p class="context-desc">Task 使用的模型 Provider 与模型将在 Phase 2 提供配置入口。</p>
              </div>
              <span class="chip chip--muted">Phase 2</span>
            </header>
            <div class="model-info">
              <span class="model-info__label">当前记录</span>
              <span class="model-info__value">{{ modelLabel }}</span>
              <span class="model-info__hint">模型切换将影响后续调用，不会改变历史 Execution 已记录的模型信息。</span>
            </div>
          </section>
        </template>
      </section>

      <!-- Artifacts -->
      <section v-else role="tabpanel" class="tab-panel">
        <div class="card">
          <EmptyState
            icon="file"
            title="Artifacts 将在 Phase 3 提供"
            description="当前 Task 还没有成果数据。Artifact 系列、版本与来源 Execution 将在 Phase 3 展示。"
          />
        </div>
      </section>

      <FilePickerModal
        :open="pickerOpen"
        :exclude-ids="pickerExcludedIds"
        title="添加额外引用文件"
        description="从 Global Library 选择文件加入当前 Task 的可用上下文，不依赖 Project 继承关系。"
        confirm-label="添加引用"
        @close="pickerOpen = false"
        @selected="addExtraFiles"
      />
    </template>
  </div>
</template>

<style scoped>
.task-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
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
  margin-bottom: 8px;
  font-size: 12px;
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
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.task-head__desc {
  margin: 8px 0 0;
  max-width: 760px;
  font-size: 13px;
  line-height: 1.6;
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
  font-size: 12px;
  color: var(--text-faint);
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
  font-size: 11.5px;
  color: var(--text-faint);
}

.tabbar {
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid var(--border);
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
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
  gap: 14px;
  padding-top: 6px;
}

.chat-panel {
  min-height: 420px;
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
  border-radius: var(--radius);
  background: var(--bg-subtle);
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
  font-size: 11.5px;
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
  border-radius: var(--radius);
  background: var(--bg-raised);
}

.context-stat__value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.2;
}

.context-stat__label {
  font-size: 11.5px;
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
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.context-desc {
  margin: 4px 0 0;
  font-size: 11.5px;
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

.file-item__name {
  font-size: 13px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-item__meta {
  font-size: 11.5px;
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
  font-size: 11.5px;
  color: var(--text-faint);
}

.model-info__value {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-secondary);
}

.model-info__hint {
  font-size: 11.5px;
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
