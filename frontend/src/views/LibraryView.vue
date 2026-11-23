<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import MarkdownText from '@/components/MarkdownText.vue'
import Modal from '@/components/Modal.vue'
import PageHeader from '@/components/PageHeader.vue'
import { deleteFile, getFile, getFileContent, listFiles, uploadFile } from '@/api/endpoints'
import type { FileContent, FileDetail, FileItem } from '@/api/types'
import { useAppStore } from '@/stores/app'
import {
  errorMessage,
  extractReferences,
  isConflict,
  isUnsupportedFileType,
  type ReferenceInfo,
} from '@/utils/errors'
import {
  SUPPORTED_FILE_ACCEPT,
  fileExtension,
  isSupportedFile,
} from '@/utils/fileTypes'
import { fileTypeLabel, formatBytes, formatDateTime } from '@/utils/format'

const app = useAppStore()

const files = ref<FileItem[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const search = ref('')
const searching = ref(false)
const typeFilter = ref('')
const sortBy = ref<'updated' | 'name' | 'size'>('updated')

const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const uploadName = ref<string | null>(null)

const previewOpen = ref(false)
const previewItem = ref<FileItem | null>(null)
const previewDetail = ref<FileDetail | null>(null)
const previewContent = ref<FileContent | null>(null)
const previewLoading = ref(false)
const previewError = ref<string | null>(null)
let previewToken = 0

const deleteTarget = ref<FileItem | null>(null)
const deleteBusy = ref(false)
const conflictOpen = ref(false)
const conflictFile = ref<string | null>(null)
const conflictRefs = ref<ReferenceInfo[]>([])

let searchTimer: number | undefined

const visibleFiles = computed(() => {
  const items = [...files.value]
  if (sortBy.value === 'name') {
    items.sort((a, b) => a.filename.localeCompare(b.filename, 'zh-CN'))
  } else if (sortBy.value === 'size') {
    items.sort((a, b) => b.size - a.size)
  } else {
    items.sort((a, b) => (b.updated_at ?? b.created_at).localeCompare(a.updated_at ?? a.created_at))
  }
  return items
})

const hasFilters = computed(() => Boolean(search.value.trim() || typeFilter.value))

const filteredCountLabel = computed(() => {
  if (search.value.trim() || typeFilter.value) return `${visibleFiles.value.length} 个匹配文件`
  return `${visibleFiles.value.length} 个文件`
})

async function load(): Promise<void> {
  loading.value = files.value.length === 0
  searching.value = true
  loadError.value = null
  try {
    files.value = await listFiles({
      search: search.value.trim() || undefined,
      file_type: typeFilter.value || undefined,
      limit: 100,
    })
  } catch (error) {
    loadError.value = errorMessage(error)
    files.value = []
  } finally {
    loading.value = false
    searching.value = false
  }
}

function pickFile(): void {
  fileInput.value?.click()
}

async function onFileSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  const extension = fileExtension(file.name)
  if (!isSupportedFile(file.name)) {
    app.notify(
      'error',
      `不支持的文件类型：.${extension || '未知'}`,
      '支持 PDF / Markdown / TXT / JSON / YAML / CSV / HTML / CSS',
    )
    return
  }

  uploading.value = true
  uploadName.value = file.name
  try {
    const uploaded = await uploadFile(file)
    app.notify('success', `文件「${uploaded.filename}」已上传`)
    if (search.value.trim()) search.value = ''
    await load()
  } catch (error) {
    if (isUnsupportedFileType(error)) {
      app.notifyError(
        error,
        '后端拒绝了该文件类型（支持 PDF / Markdown / TXT / JSON / YAML / CSV / HTML / CSS）',
      )
    } else {
      app.notifyError(error)
    }
  } finally {
    uploading.value = false
    uploadName.value = null
  }
}

async function openPreview(file: FileItem): Promise<void> {
  previewOpen.value = true
  previewItem.value = file
  previewDetail.value = null
  previewContent.value = null
  previewError.value = null
  previewLoading.value = true
  const token = ++previewToken
  const [detailResult, contentResult] = await Promise.allSettled([
    getFile(file.id),
    getFileContent(file.id),
  ])
  if (token !== previewToken) return
  if (detailResult.status === 'fulfilled') {
    previewDetail.value = detailResult.value
  }
  if (contentResult.status === 'fulfilled') {
    previewContent.value = contentResult.value
  } else {
    previewError.value = errorMessage(contentResult.reason)
  }
  previewLoading.value = false
}

async function retryPreview(): Promise<void> {
  if (previewItem.value) await openPreview(previewItem.value)
}

function closePreview(): void {
  previewOpen.value = false
  previewToken += 1
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value
  if (!target) return
  deleteBusy.value = true
  try {
    await deleteFile(target.id)
    app.notify('success', `文件「${target.filename}」已删除`)
    deleteTarget.value = null
    if (previewOpen.value && previewItem.value?.id === target.id) closePreview()
    await load()
  } catch (error) {
    deleteTarget.value = null
    if (isConflict(error)) {
      conflictFile.value = target.filename
      conflictRefs.value = extractReferences(error)
      conflictOpen.value = true
    } else {
      app.notifyError(error)
    }
  } finally {
    deleteBusy.value = false
  }
}

function referenceKindLabel(kind: string): string {
  if (kind === 'project') return 'Project'
  if (kind === 'task') return 'Task'
  return kind
}

watch(search, () => {
  if (searchTimer !== undefined) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void load(), 320)
})
watch(typeFilter, () => {
  void load()
})

onMounted(() => {
  void load()
})

onBeforeUnmount(() => {
  if (searchTimer !== undefined) window.clearTimeout(searchTimer)
})
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Library"
      description="统一文件资料库。Project 与 Task 通过引用使用文件，上传到 Library 不会自动让所有任务读取该文件。"
    >
      <template #actions>
        <button type="button" class="btn btn--ghost btn--icon" title="刷新" @click="load">
          <AppIcon name="refresh" :size="16" />
        </button>
        <button type="button" class="btn btn--primary" :disabled="uploading" @click="pickFile">
          <span v-if="uploading" class="spinner spinner--sm" aria-hidden="true" />
          <AppIcon v-else name="upload" :size="16" />
          {{ uploading ? '上传中…' : '上传文件' }}
        </button>
        <input
          ref="fileInput"
          type="file"
          class="visually-hidden"
          :accept="SUPPORTED_FILE_ACCEPT"
          @change="onFileSelected"
        />
      </template>
    </PageHeader>

    <div class="toolbar">
      <div class="search-box">
        <AppIcon name="search" :size="15" />
        <input
          v-model="search"
          type="search"
          class="search-box__input"
          placeholder="搜索文件名…"
          aria-label="搜索文件"
        />
        <span v-if="searching" class="spinner spinner--sm" aria-hidden="true" />
      </div>
      <select v-model="typeFilter" class="select toolbar__select" aria-label="按类型筛选">
        <option value="">全部类型</option>
        <option value="pdf">PDF</option>
        <option value="md">Markdown</option>
        <option value="txt">TXT</option>
        <option value="json">JSON</option>
        <option value="yaml">YAML</option>
        <option value="csv">CSV</option>
        <option value="html">HTML</option>
        <option value="css">CSS</option>
      </select>
      <select v-model="sortBy" class="select toolbar__select" aria-label="排序方式">
        <option value="updated">最近更新</option>
        <option value="name">文件名</option>
        <option value="size">文件大小</option>
      </select>
      <span class="toolbar__count">{{ filteredCountLabel }}</span>
    </div>

    <p class="upload-note">
      支持 PDF / Markdown / TXT / JSON / YAML / CSV / HTML / CSS；其他格式会被明确拒绝，不会静默忽略。
      <span v-if="uploading && uploadName" class="upload-note__active">正在上传：{{ uploadName }}</span>
    </p>

    <LoadingState v-if="loading" label="正在加载文件…" />

    <div v-else-if="loadError" class="panel panel--error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">文件列表加载失败</p>
        <p class="panel--error__desc">{{ loadError }}</p>
      </div>
      <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
    </div>

    <EmptyState
      v-else-if="visibleFiles.length === 0 && !hasFilters"
      icon="library"
      title="Library 还没有文件"
      description="上传文档、结构化数据或设计文本，之后可在 Project 和 Task 中引用它们。"
    >
      <button type="button" class="btn btn--primary" :disabled="uploading" @click="pickFile">
        <AppIcon name="upload" :size="16" />
        上传第一个文件
      </button>
    </EmptyState>

    <EmptyState
      v-else-if="visibleFiles.length === 0"
      icon="search"
      title="没有匹配的文件"
      description="尝试其他关键词或类型筛选，或清空条件查看全部文件。"
    >
      <button type="button" class="btn btn--ghost" @click="search = ''; typeFilter = ''">
        清空筛选
      </button>
    </EmptyState>

    <div v-else class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>文件</th>
            <th>类型</th>
            <th>大小</th>
            <th>上传时间</th>
            <th class="table__actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="file in visibleFiles" :key="file.id">
            <td>
              <button type="button" class="cell-file" @click="openPreview(file)">
                <span class="cell-file__icon"><AppIcon name="file" :size="14" /></span>
                <span class="cell-file__name" :title="file.filename">{{ file.filename }}</span>
              </button>
            </td>
            <td><span class="chip">{{ fileTypeLabel(file.file_type) }}</span></td>
            <td class="cell-muted">{{ formatBytes(file.size) }}</td>
            <td class="cell-muted">{{ formatDateTime(file.created_at) }}</td>
            <td class="table__actions">
              <button type="button" class="btn btn--ghost btn--sm" @click="deleteTarget = file">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Modal
      :open="previewOpen"
      :title="previewItem?.filename ?? '文件预览'"
      width="880px"
      @close="closePreview"
    >
      <div v-if="previewItem" class="preview">
        <div class="preview-meta">
          <span class="chip">{{ fileTypeLabel(previewItem.file_type) }}</span>
          <span class="preview-meta__item">{{ formatBytes(previewItem.size) }}</span>
          <span class="preview-meta__item">上传于 {{ formatDateTime(previewItem.created_at) }}</span>
          <span class="preview-meta__item preview-meta__mono">{{ previewItem.mime_type }}</span>
        </div>

        <div v-if="previewDetail && previewDetail.references.length > 0" class="preview-refs">
          <span class="preview-refs__label">被引用：</span>
          <span v-for="ref in previewDetail.references" :key="`${ref.kind}-${ref.id}`" class="chip chip--muted">
            {{ referenceKindLabel(ref.kind) }} · {{ ref.name }}
          </span>
        </div>

        <div v-if="previewLoading" class="preview-loading">
          <LoadingState label="正在读取文件内容…" compact />
        </div>

        <div v-else-if="previewError" class="preview-error">
          <AppIcon name="alert" :size="16" />
          <div>
            <p class="preview-error__title">内容读取失败</p>
            <p class="preview-error__desc">{{ previewError }}</p>
          </div>
          <button type="button" class="btn btn--ghost btn--sm" @click="retryPreview">重试</button>
        </div>

        <template v-else-if="previewContent">
          <div v-if="previewContent.truncated" class="notice notice--warning">
            <AppIcon name="info" :size="15" />
            <span>文件内容超过展示上限，仅显示前 20,000 个字符。</span>
          </div>
          <div class="preview-content">
            <MarkdownText v-if="previewContent.text.trim()" :text="previewContent.text" />
            <p v-else class="preview-empty">该文件没有可提取的文本内容。</p>
          </div>
        </template>

        <EmptyState
          v-else
          icon="file"
          title="暂无可展示的内容"
          description="该文件暂时无法生成文本预览。"
          compact
        />
      </div>
    </Modal>

    <ConfirmDialog
      :open="deleteTarget !== null"
      title="删除文件"
      :message="`确定删除「${deleteTarget?.filename ?? ''}」吗？\n\n删除会影响所有引用该文件的 Project 与 Task；若文件仍被引用，删除会被后端拒绝。`"
      confirm-label="删除"
      danger
      :busy="deleteBusy"
      @close="deleteTarget = null"
      @confirm="confirmDelete"
    />

    <Modal
      :open="conflictOpen"
      title="无法删除文件"
      width="560px"
      @close="conflictOpen = false"
    >
      <p class="conflict-message">
        「{{ conflictFile }}」仍被以下 Project / Task 引用，请先解除关联后再删除。
      </p>
      <ul v-if="conflictRefs.length > 0" class="conflict-list">
        <li v-for="ref in conflictRefs" :key="`${ref.kind}-${ref.id}`">
          <span class="chip">{{ referenceKindLabel(ref.kind) }}</span>
          <span class="conflict-list__name">{{ ref.name }}</span>
        </li>
      </ul>
      <p v-else class="conflict-message">
        后端拒绝了删除操作（409 Conflict），但未返回引用清单。
      </p>
      <template #footer>
        <button type="button" class="btn btn--ghost" @click="conflictOpen = false">知道了</button>
      </template>
    </Modal>
  </div>
</template>

<style scoped>
.library-page {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  width: min(380px, 100%);
  padding: 0 10px;
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

.toolbar__select {
  width: auto;
  min-width: 110px;
}

.toolbar__count {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.upload-note {
  margin: 0 0 16px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.6;
}

.upload-note__active {
  margin-left: 8px;
  color: var(--accent);
}

.table-wrap {
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  border-radius: 0;
  background: transparent;
  overflow: hidden;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.table th {
  padding: 12px 10px;
  text-align: left;
  font-family: var(--font-mono);
  font-weight: 500;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  background: transparent;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.table td {
  padding: 12px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-secondary);
  vertical-align: middle;
}

.table tbody tr:last-child td {
  border-bottom: none;
}

.table tbody tr:hover {
  background: var(--bg-subtle);
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
  padding: 0;
  border: none;
  background: transparent;
  font: inherit;
  color: inherit;
  cursor: pointer;
  text-align: left;
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

.cell-file:hover .cell-file__name {
  color: var(--accent);
}

.cell-muted {
  color: var(--text-muted);
  white-space: nowrap;
}

.preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.preview-meta__item {
  font-size: 12px;
  color: var(--text-faint);
}

.preview-meta__mono {
  font-family: var(--font-mono);
}

.preview-refs {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-faint);
}

.preview-refs__label {
  color: var(--text-faint);
}

.preview-loading {
  padding: 20px 0;
}

.preview-error {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px;
  border: 1px solid rgba(242, 105, 92, 0.35);
  border-radius: var(--radius-sm);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: 12.5px;
}

.preview-error p {
  margin: 0;
}

.preview-error__title {
  font-weight: 600;
}

.preview-error__desc {
  margin-top: 3px !important;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.preview-error .btn {
  margin-left: auto;
  flex-shrink: 0;
}

.preview-content {
  max-height: 56vh;
  overflow-y: auto;
  padding: 4px 2px;
}

.preview-empty {
  margin: 0;
  padding: 24px 0;
  text-align: center;
  color: var(--text-faint);
  font-size: 12.5px;
}

.notice {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 10px 13px;
  border: 1px solid var(--warning);
  border-radius: var(--radius-sm);
  background: var(--warning-soft);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.notice--warning {
  border-color: rgba(217, 164, 65, 0.35);
}

.notice :deep(svg) {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--warning);
}

.conflict-message {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.65;
}

.conflict-list {
  list-style: none;
  margin: 12px 0 0;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  max-height: 240px;
  overflow-y: auto;
}

.conflict-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 9px;
  font-size: 12.5px;
}

.conflict-list__name {
  color: var(--text-secondary);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}
</style>
