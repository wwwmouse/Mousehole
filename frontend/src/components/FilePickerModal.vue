<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import Modal from '@/components/Modal.vue'
import { listFiles } from '@/api/endpoints'
import type { FileItem } from '@/api/types'
import { errorMessage } from '@/utils/errors'
import { fileTypeLabel, formatBytes, formatDate } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    description?: string
    excludeIds?: string[]
    confirmLabel?: string
  }>(),
  {
    title: '从 Library 选择文件',
    description: '选择只建立引用关系，不会复制或移动原始文件。',
    excludeIds: () => [],
    confirmLabel: '添加',
  },
)

const emit = defineEmits<{ close: []; selected: [files: FileItem[]] }>()

const search = ref('')
const files = ref<FileItem[]>([])
const loading = ref(false)
const loadError = ref<string | null>(null)
const selectedIds = ref<string[]>([])

const excluded = computed(() => new Set(props.excludeIds))

const visibleFiles = computed(() => files.value.filter((file) => !excluded.value.has(file.id)))

const allSelected = computed(
  () => visibleFiles.value.length > 0 && selectedIds.value.length === visibleFiles.value.length,
)

const selectedCount = computed(() => selectedIds.value.length)

let debounceTimer: number | undefined

function toggle(fileId: string): void {
  selectedIds.value = selectedIds.value.includes(fileId)
    ? selectedIds.value.filter((id) => id !== fileId)
    : [...selectedIds.value, fileId]
}

function toggleAll(): void {
  selectedIds.value = allSelected.value ? [] : visibleFiles.value.map((file) => file.id)
}

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    files.value = await listFiles({ search: search.value.trim() || undefined, limit: 100 })
    selectedIds.value = selectedIds.value.filter((id) => files.value.some((file) => file.id === id))
  } catch (error) {
    loadError.value = errorMessage(error)
    files.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      search.value = ''
      selectedIds.value = []
      void load()
    }
  },
)

watch(search, () => {
  if (!props.open) return
  if (debounceTimer !== undefined) window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => void load(), 280)
})

function onConfirm(): void {
  const selected = files.value.filter((file) => selectedIds.value.includes(file.id))
  if (selected.length === 0) return
  emit('selected', selected)
}

function onClose(): void {
  emit('close')
}
</script>

<template>
  <Modal :open="open" :title="title" width="720px" :dismissible="true" @close="onClose">
    <div class="picker">
      <p class="picker-desc">{{ description }}</p>
      <div class="picker-toolbar">
        <div class="search-box">
          <AppIcon name="search" :size="15" />
          <input
            v-model="search"
            type="search"
            class="search-box__input"
            placeholder="搜索文件名…"
            aria-label="搜索文件"
          />
        </div>
        <button
          v-if="visibleFiles.length > 0"
          type="button"
          class="btn btn--ghost btn--sm"
          @click="toggleAll"
        >
          {{ allSelected ? '取消全选' : '全选' }}
        </button>
      </div>

      <div class="picker-list">
        <LoadingState v-if="loading" label="正在加载文件…" compact />
        <div v-else-if="loadError" class="picker-error">
          <p>{{ loadError }}</p>
          <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
        </div>
        <EmptyState
          v-else-if="visibleFiles.length === 0"
          icon="file"
          :title="search ? '没有匹配的文件' : 'Library 中还没有文件'"
          :description="search ? '尝试其他关键词，或先在 Library 上传文件。' : '请先在 Library 上传文档、结构化数据或设计文本文件。'"
          compact
        />
        <ul v-else class="file-rows">
          <li v-for="file in visibleFiles" :key="file.id">
            <label class="file-row" :class="{ 'file-row--selected': selectedIds.includes(file.id) }">
              <input
                type="checkbox"
                class="checkbox"
                :checked="selectedIds.includes(file.id)"
                @change="toggle(file.id)"
              />
              <span class="file-row__icon">
                <AppIcon name="file" :size="15" />
              </span>
              <span class="file-row__main">
                <span class="file-row__name" :title="file.filename">{{ file.filename }}</span>
                <span class="file-row__meta">
                  {{ fileTypeLabel(file.file_type) }} · {{ formatBytes(file.size) }} · {{ formatDate(file.created_at) }}
                </span>
              </span>
            </label>
          </li>
        </ul>
      </div>
    </div>

    <template #footer>
      <span class="picker-count">{{ selectedCount > 0 ? `已选择 ${selectedCount} 个文件` : '未选择文件' }}</span>
      <button type="button" class="btn btn--ghost" @click="onClose">取消</button>
      <button type="button" class="btn btn--primary" :disabled="selectedCount === 0" @click="onConfirm">
        {{ confirmLabel }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.picker {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.picker-desc {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.picker-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
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
  height: 32px;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 13px;
  outline: none;
}

.picker-list {
  max-height: 46vh;
  min-height: 140px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
}

.picker-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  color: var(--danger);
  font-size: 13px;
}

.picker-error p {
  margin: 0;
}

.file-rows {
  list-style: none;
  margin: 0;
  padding: 4px;
}

.file-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.13s ease;
}

.file-row:hover {
  background: var(--bg-hover);
}

.file-row--selected {
  background: var(--accent-soft);
}

.checkbox {
  width: 14px;
  height: 14px;
  accent-color: var(--accent);
  flex-shrink: 0;
}

.file-row__icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-raised);
  color: var(--text-muted);
}

.file-row__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.file-row__name {
  font-size: 13px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-row__meta {
  font-size: 12px;
  color: var(--text-faint);
}

.picker-count {
  margin-right: auto;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
