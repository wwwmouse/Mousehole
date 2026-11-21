<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import EntityMenu from '@/components/EntityMenu.vue'
import FilePickerModal from '@/components/FilePickerModal.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  addProjectFile,
  createTask,
  deleteProject,
  deleteTask,
  getProject,
  listProjectArtifactSeries,
  listProjectFiles,
  listTasks,
  removeProjectFile,
  updateProject,
  updateTask,
} from '@/api/endpoints'
import type { ArtifactSeries, FileItem, Project, ProjectFile, Task } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage, isNotFound } from '@/utils/errors'
import { fileTypeLabel, formatBytes, formatDateTime, formatDate, formatRelative } from '@/utils/format'

type TabKey = 'overview' | 'tasks' | 'files' | 'artifacts'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const projectId = computed(() => String(route.params.id ?? ''))

const project = ref<Project | null>(null)
const files = ref<ProjectFile[]>([])
const tasks = ref<Task[]>([])
const seriesList = ref<ArtifactSeries[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const notFound = ref(false)

const activeTab = ref<TabKey>('overview')
const pickerOpen = ref(false)
const addingFiles = ref(false)

const archiveOpen = ref(false)
const archiveBusy = ref(false)

const removeTarget = ref<ProjectFile | null>(null)
const removeBusy = ref(false)

const recentTasks = computed(() =>
  [...tasks.value]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 5),
)
const recentSeries = computed(() =>
  [...seriesList.value]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 5),
)

const tabItems = computed(() => [
  { key: 'overview' as TabKey, label: 'Overview', count: null },
  { key: 'tasks' as TabKey, label: 'Tasks', count: tasks.value.length },
  { key: 'files' as TabKey, label: 'Files', count: files.value.length },
  { key: 'artifacts' as TabKey, label: 'Artifacts', count: seriesList.value.length },
])

const isArchived = computed(() => project.value?.status === 'archived')

const excludedFileIds = computed(() => files.value.map((item) => item.file.id))

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  notFound.value = false
  const id = projectId.value
  if (!id) {
    notFound.value = true
    loading.value = false
    return
  }
  try {
    const [projectResult, fileResult, taskResult, seriesResult] =
      await Promise.all([
        getProject(id),
        listProjectFiles(id),
        listTasks({ project_id: id, limit: 200 }),
        listProjectArtifactSeries(id),
      ])
    project.value = projectResult
    files.value = fileResult
    tasks.value = taskResult
    seriesList.value = seriesResult
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

async function reloadFiles(): Promise<void> {
  if (!project.value) return
  try {
    files.value = await listProjectFiles(project.value.id)
  } catch (error) {
    app.notifyError(error)
  }
}

async function toggleArchive(): Promise<void> {
  if (!project.value) return
  archiveBusy.value = true
  try {
    const nextStatus = project.value.status === 'archived' ? 'active' : 'archived'
    project.value = await updateProject(project.value.id, { status: nextStatus })
    app.notify('success', nextStatus === 'archived' ? '项目已归档' : '项目已取消归档')
    archiveOpen.value = false
  } catch (error) {
    app.notifyError(error)
  } finally {
    archiveBusy.value = false
  }
}

async function addFiles(selected: FileItem[]): Promise<void> {
  if (!project.value || selected.length === 0) return
  addingFiles.value = true
  let added = 0
  const failures: string[] = []
  for (const file of selected) {
    try {
      await addProjectFile(project.value.id, file.id)
      added += 1
    } catch (error) {
      failures.push(`${file.filename}：${errorMessage(error)}`)
    }
  }
  pickerOpen.value = false
  addingFiles.value = false
  if (added > 0) {
    app.notify('success', `已添加 ${added} 个文件到项目`)
    await reloadFiles()
    try {
      project.value = await getProject(project.value.id)
    } catch {
      /* counts refresh is best-effort */
    }
  }
  for (const failure of failures) {
    app.notify('error', failure)
  }
}

async function confirmRemoveFile(): Promise<void> {
  const target = removeTarget.value
  if (!project.value || !target) return
  removeBusy.value = true
  try {
    await removeProjectFile(project.value.id, target.file.id)
    app.notify('success', `已从项目移除「${target.file.filename}」`)
    removeTarget.value = null
    await reloadFiles()
    try {
      project.value = await getProject(project.value.id)
    } catch {
      /* counts refresh is best-effort */
    }
  } catch (error) {
    app.notifyError(error)
  } finally {
    removeBusy.value = false
  }
}

function taskTitle(taskId: string): string {
  const found = tasks.value.find((item) => item.id === taskId)
  return found?.title ?? '未知 Task'
}

function openTask(task: Task): void {
  void router.push({ name: 'task', params: { id: task.id } })
}

async function createProjectTask(): Promise<void> {
  if (!project.value) return
  const number = tasks.value.length + 1
  try {
    const created = await createTask({
      project_id: project.value.id,
      title: `${project.value.name}-task${number}`,
    })
    app.notify('success', `已创建任务「${created.title}」`)
    void router.push({ name: 'task', params: { id: created.id } })
  } catch (error) {
    app.notifyError(error)
  }
}

async function renameProject(name: string): Promise<void> {
  if (!project.value) return
  try {
    project.value = await updateProject(project.value.id, { name })
    app.notify('success', '项目已重命名')
  } catch (error) {
    app.notifyError(error)
  }
}

async function removeProject(): Promise<void> {
  if (!project.value) return
  try {
    await deleteProject(project.value.id)
    app.notify('success', '项目已删除')
    void router.replace('/projects')
  } catch (error) {
    app.notifyError(error)
  }
}

async function renameTaskInProject(item: Task, name: string): Promise<void> {
  try {
    const updated = await updateTask(item.id, { title: name })
    tasks.value = tasks.value.map((t) => (t.id === updated.id ? updated : t))
    app.notify('success', '任务已重命名')
  } catch (error) {
    app.notifyError(error)
  }
}

async function toggleTaskArchiveInProject(item: Task): Promise<void> {
  const next = item.status === 'archived' ? 'active' : 'archived'
  try {
    const updated = await updateTask(item.id, { status: next })
    tasks.value = tasks.value.map((t) => (t.id === updated.id ? updated : t))
    app.notify('success', next === 'archived' ? '任务已归档' : '任务已取消归档')
  } catch (error) {
    app.notifyError(error)
  }
}

async function removeTaskInProject(item: Task): Promise<void> {
  try {
    await deleteTask(item.id)
    tasks.value = tasks.value.filter((t) => t.id !== item.id)
    app.notify('success', '任务已删除')
    try {
      if (project.value) project.value = await getProject(project.value.id)
    } catch {
      /* 计数刷新尽力而为 */
    }
  } catch (error) {
    app.notifyError(error)
  }
}

function taskModel(task: Task): string {
  if (!task.model_name) return '未配置模型'
  return task.model_provider ? `${task.model_provider} / ${task.model_name}` : task.model_name
}

watch(projectId, () => {
  activeTab.value = 'tasks'
  void load()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="project-detail">
    <LoadingState v-if="loading" label="正在加载项目…" />

    <div v-else-if="notFound" class="state-page">
      <EmptyState
        icon="folder"
        title="项目不存在"
        description="该项目可能已被删除，或链接无效。"
      >
        <RouterLink to="/projects" class="btn btn--ghost">返回 Projects</RouterLink>
      </EmptyState>
    </div>

    <div v-else-if="loadError" class="panel panel--error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">项目加载失败</p>
        <p class="panel--error__desc">{{ loadError }}</p>
      </div>
      <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
    </div>

    <template v-else-if="project">
      <PageHeader
        :title="project.name"
        :description="project.description || '暂无项目描述'"
        back-to="/projects"
        back-label="Projects"
      >
        <template #meta>
          <StatusBadge :status="project.status" kind="project" />
          <span class="meta-item">{{ project.task_count }} 个 Task</span>
          <span class="meta-item">{{ project.file_count }} 个文件</span>
          <span class="meta-item">创建于 {{ formatDate(project.created_at) }}</span>
        </template>
        <template #actions>
          <button
            v-if="isArchived"
            type="button"
            class="btn btn--ghost"
            :disabled="archiveBusy"
            @click="toggleArchive"
          >
            <span v-if="archiveBusy" class="spinner spinner--sm" aria-hidden="true" />
            取消归档
          </button>
          <button v-else type="button" class="btn btn--ghost" @click="archiveOpen = true">
            <AppIcon name="archive" :size="15" />
            归档项目
          </button>
          <EntityMenu
            :name="project.name"
            kind="project"
            :archived="isArchived"
            @rename="renameProject"
            @toggle-archive="toggleArchive"
            @remove="removeProject"
          />
        </template>
      </PageHeader>

      <div v-if="isArchived" class="notice notice--muted">
        <AppIcon name="archive" :size="15" />
        <span>该项目已归档。归档不会删除项目内容，可随时取消归档。</span>
      </div>

      <div class="tabbar" role="tablist" aria-label="项目分区">
        <button
          v-for="tab in tabItems"
          :key="tab.key"
          type="button"
          role="tab"
          class="tab"
          :class="{ 'tab--active': activeTab === tab.key }"
          :aria-selected="activeTab === tab.key"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span v-if="tab.count !== null" class="tab__count">{{ tab.count }}</span>
        </button>
      </div>

      <section v-if="activeTab === 'overview'" role="tabpanel" class="tab-panel">
        <div class="overview-grid">
          <article class="card overview-card">
            <span class="overview-card__label">Tasks</span>
            <span class="overview-card__value">{{ tasks.length }}</span>
          </article>
          <article class="card overview-card">
            <span class="overview-card__label">Files</span>
            <span class="overview-card__value">{{ files.length }}</span>
          </article>
          <article class="card overview-card">
            <span class="overview-card__label">Artifacts</span>
            <span class="overview-card__value">{{ seriesList.length }}</span>
          </article>
        </div>

        <section class="card overview-section">
          <header class="section-head">
            <h2 class="context-title">最近活动</h2>
            <span class="section-caption">最近更新的 Task 与成果</span>
          </header>
          <div class="overview-columns">
            <div>
              <p class="overview-subtitle">最近 Tasks</p>
              <p v-if="recentTasks.length === 0" class="overview-empty">暂无 Task</p>
              <ul v-else class="overview-list">
                <li v-for="task in recentTasks" :key="task.id">
                  <button type="button" class="overview-row" @click="openTask(task)">
                    <span class="overview-row__title">{{ task.title }}</span>
                    <span class="overview-row__meta">{{ formatRelative(task.updated_at) }}</span>
                  </button>
                </li>
              </ul>
            </div>
            <div>
              <p class="overview-subtitle">最近成果</p>
              <p v-if="recentSeries.length === 0" class="overview-empty">暂无成果</p>
              <ul v-else class="overview-list">
                <li v-for="series in recentSeries" :key="series.id">
                  <button
                    type="button"
                    class="overview-row"
                    @click="
                      router.push({
                        name: 'task',
                        params: { id: series.task_id },
                        query: { tab: 'artifacts' },
                      })
                    "
                  >
                    <span class="overview-row__title">{{ series.title }}</span>
                    <span class="overview-row__meta">{{ formatRelative(series.updated_at) }}</span>
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </section>
      </section>

      <section v-if="activeTab === 'tasks'" role="tabpanel" class="tab-panel">
        <div class="section-toolbar">
          <p class="section-hint">项目内的 Task 会自动关联本项目，并继承项目文件作为可用上下文。</p>
          <button type="button" class="btn btn--primary btn--sm" @click="createProjectTask">
            <AppIcon name="plus" :size="15" />
            新建 Task
          </button>
        </div>

        <EmptyState
          v-if="tasks.length === 0"
          icon="sparkles"
          title="该项目还没有 Task"
          description="创建一个 Task，基于项目资料开始一次有明确目标的工作。"
        >
          <button type="button" class="btn btn--primary" @click="createProjectTask">
            <AppIcon name="plus" :size="16" />
            新建 Task
          </button>
        </EmptyState>

        <ul v-else class="item-list">
          <li v-for="task in tasks" :key="task.id" class="item-row-item">
            <button type="button" class="item-row" @click="openTask(task)">
              <span class="item-row__icon"><AppIcon name="sparkles" :size="15" /></span>
              <span class="item-row__main">
                <span class="item-row__title">{{ task.title }}</span>
                <span class="item-row__meta">
                  {{ taskModel(task) }} · 更新于 {{ formatDateTime(task.updated_at) }}
                </span>
              </span>
              <StatusBadge :status="task.status" kind="task" />
              <AppIcon name="chevron-right" :size="15" class="item-row__chevron" />
            </button>
            <EntityMenu
              :name="task.title"
              kind="task"
              :archived="task.status === 'archived'"
              @rename="(name) => renameTaskInProject(task, name)"
              @toggle-archive="() => toggleTaskArchiveInProject(task)"
              @remove="() => removeTaskInProject(task)"
            />
          </li>
        </ul>
      </section>

      <section v-if="activeTab === 'files'" role="tabpanel" class="tab-panel">
        <div class="section-toolbar">
          <p class="section-hint">
            Project 文件是项目内 Task 的默认可用上下文来源；移除关联不会删除 Library 中的原始文件。
          </p>
          <button type="button" class="btn btn--primary btn--sm" :disabled="addingFiles" @click="pickerOpen = true">
            <AppIcon name="plus" :size="15" />
            从 Library 添加
          </button>
        </div>

        <EmptyState
          v-if="files.length === 0"
          icon="file"
          title="项目还没有关联文件"
          description="从 Global Library 选择文件加入项目，项目内的 Task 将默认获得这些文件作为可用上下文。"
        >
          <button type="button" class="btn btn--primary" @click="pickerOpen = true">
            <AppIcon name="plus" :size="16" />
            从 Library 添加
          </button>
        </EmptyState>

        <div v-else class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>文件</th>
                <th>类型</th>
                <th>大小</th>
                <th>添加时间</th>
                <th class="table__actions">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in files" :key="item.file.id">
                <td>
                  <div class="cell-file">
                    <span class="cell-file__icon"><AppIcon name="file" :size="14" /></span>
                    <span class="cell-file__name" :title="item.file.filename">{{ item.file.filename }}</span>
                  </div>
                </td>
                <td><span class="chip">{{ fileTypeLabel(item.file.file_type) }}</span></td>
                <td class="cell-muted">{{ formatBytes(item.file.size) }}</td>
                <td class="cell-muted">{{ formatDateTime(item.added_at) }}</td>
                <td class="table__actions">
                  <button
                    type="button"
                    class="btn btn--ghost btn--sm"
                    @click="removeTarget = item"
                  >
                    移除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="activeTab === 'artifacts'" role="tabpanel" class="tab-panel">
        <EmptyState
          v-if="seriesList.length === 0"
          icon="file"
          title="项目还没有成果"
          description="项目内 Task 执行 Skill 后产生的成果会汇总到这里。"
        />
        <ul v-else class="item-list">
          <li v-for="series in seriesList" :key="series.id">
            <button
              type="button"
              class="item-row"
              @click="
                router.push({
                  name: 'task',
                  params: { id: series.task_id },
                  query: { tab: 'artifacts' },
                })
              "
            >
              <span class="item-row__icon"><AppIcon name="file" :size="15" /></span>
              <span class="item-row__main">
                <span class="item-row__title">{{ series.title }}</span>
                <span class="item-row__meta">
                  {{ taskTitle(series.task_id) }} · 更新于
                  {{ formatDateTime(series.updated_at) }}
                </span>
              </span>
              <AppIcon name="chevron-right" :size="15" class="item-row__chevron" />
            </button>
          </li>
        </ul>
      </section>

      <FilePickerModal
        :open="pickerOpen"
        :exclude-ids="excludedFileIds"
        confirm-label="添加到项目"
        @close="pickerOpen = false"
        @selected="addFiles"
      />

      <ConfirmDialog
        :open="archiveOpen"
        title="归档项目"
        message="归档后项目将标记为「已归档」，但内容不会被删除，可随时取消归档。确定归档吗？"
        confirm-label="归档"
        :busy="archiveBusy"
        @close="archiveOpen = false"
        @confirm="toggleArchive"
      />

      <ConfirmDialog
        :open="removeTarget !== null"
        title="移除项目文件关联"
        :message="`确定从项目中移除「${removeTarget?.file.filename ?? ''}」吗？\n\n仅解除项目引用，不会删除 Global Library 中的原始文件。`"
        confirm-label="移除关联"
        danger
        :busy="removeBusy"
        @close="removeTarget = null"
        @confirm="confirmRemoveFile"
      />
    </template>
  </div>
</template>

<style scoped>
.project-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.state-page {
  padding-top: 24px;
}

.meta-item {
  font-size: 12px;
  color: var(--text-faint);
}

.tabbar {
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 4px;
}

.tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 12px;
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

.tab__count {
  padding: 0 6px;
  border-radius: 999px;
  background: var(--bg-active);
  color: var(--text-muted);
  font-size: 11px;
  line-height: 17px;
}

.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 8px;
}

.section-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.section-hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.55;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.overview-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
}

.overview-card__label {
  font-size: 11.5px;
  color: var(--text-muted);
}

.overview-card__value {
  font-size: 22px;
  font-weight: 600;
}

.overview-section {
  padding: 16px;
}

.overview-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  margin-top: 10px;
}

.overview-subtitle {
  margin: 0 0 6px;
  font-size: 11px;
  color: var(--text-faint);
}

.overview-empty {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.overview-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.overview-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.overview-row:hover {
  border-color: var(--border);
  background: var(--bg-hover);
}

.overview-row__title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.overview-row__meta {
  font-size: 10.5px;
  color: var(--text-faint);
}

.item-list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-raised);
  overflow: hidden;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 13px 14px;
  border: none;
  border-bottom: 1px solid var(--border);
  background: transparent;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: inherit;
  transition: background 0.13s ease;
}

.item-list li:last-child .item-row {
  border-bottom: none;
}

.item-row:hover {
  background: var(--bg-hover);
}

.item-row__icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-muted);
}

.item-row__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.item-row__title {
  font-size: 13px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-row__meta {
  font-size: 11.5px;
  color: var(--text-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-row__chevron {
  color: var(--text-faint);
  flex-shrink: 0;
}

.table-wrap {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-raised);
  overflow: hidden;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}

.table th {
  padding: 10px 14px;
  text-align: left;
  font-weight: 500;
  font-size: 11.5px;
  color: var(--text-faint);
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text-secondary);
  vertical-align: middle;
}

.table tbody tr:last-child td {
  border-bottom: none;
}

.table tbody tr:hover {
  background: var(--bg-hover);
}

.table__actions {
  text-align: right;
  white-space: nowrap;
}

.cell-file {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.cell-file__icon {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: 5px;
  background: var(--bg-subtle);
  color: var(--text-muted);
}

.cell-file__name {
  color: var(--text);
  max-width: 420px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cell-muted {
  color: var(--text-muted);
  white-space: nowrap;
}

.item-row-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-row-item .item-row {
  flex: 1;
  min-width: 0;
}
</style>
