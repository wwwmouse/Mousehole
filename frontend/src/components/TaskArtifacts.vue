<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import MarkdownText from '@/components/MarkdownText.vue'
import Modal from '@/components/Modal.vue'
import {
  artifactDownloadUrl,
  deleteArtifact,
  exportArtifactToLibrary,
  getArtifactSeries,
  listArtifactSeries,
  renameArtifactSeries,
} from '@/api/endpoints'
import type { Artifact, ArtifactSeries, ArtifactSeriesDetail } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ taskId: string }>()
const emit = defineEmits<{ 'open-source-message': [messageId: string] }>()

const app = useAppStore()

const seriesList = ref<ArtifactSeries[]>([])
const selected = ref<ArtifactSeriesDetail | null>(null)
const selectedArtifact = ref<Artifact | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const renameOpen = ref(false)
const renameDraft = ref('')
const renaming = ref(false)

const deleteTarget = ref<Artifact | null>(null)
const deleting = ref(false)
const exporting = ref(false)

function downloadCurrent(): void {
  if (!selectedArtifact.value) return
  window.location.assign(artifactDownloadUrl(selectedArtifact.value.id))
}

async function storeToLibrary(): Promise<void> {
  const target = selectedArtifact.value
  if (!target || exporting.value) return
  exporting.value = true
  try {
    const file = await exportArtifactToLibrary(target.id)
    app.notify('success', `已存入 Library：${file.filename}`)
  } catch (err) {
    app.notifyError(err)
  } finally {
    exporting.value = false
  }
}

async function confirmDeleteArtifact(): Promise<void> {
  const target = deleteTarget.value
  if (!target) return
  deleting.value = true
  try {
    await deleteArtifact(target.id)
    deleteTarget.value = null
    app.notify('success', '成果已删除')
    await loadSeries()
  } catch (err) {
    app.notifyError(err)
  } finally {
    deleting.value = false
  }
}

const versions = computed(() => selected.value?.artifacts ?? [])

async function loadSeries(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    seriesList.value = await listArtifactSeries(props.taskId)
    if (seriesList.value.length === 0) {
      selected.value = null
      selectedArtifact.value = null
      return
    }
    const currentId = selected.value?.id
    const target =
      seriesList.value.find((item) => item.id === currentId) ?? seriesList.value[0]
    await selectSeries(target.id)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function selectSeries(seriesId: string): Promise<void> {
  try {
    const detail = await getArtifactSeries(seriesId)
    selected.value = detail
    selectedArtifact.value = detail.artifacts[0] ?? null
  } catch (err) {
    error.value = errorMessage(err)
  }
}

function openRename(): void {
  if (!selected.value) return
  renameDraft.value = selected.value.title
  renameOpen.value = true
}

async function submitRename(): Promise<void> {
  const current = selected.value
  const title = renameDraft.value.trim()
  if (!current || !title) return
  renaming.value = true
  try {
    await renameArtifactSeries(current.id, title)
    renameOpen.value = false
    app.notify('success', '系列标题已更新')
    await loadSeries()
  } catch (err) {
    app.notifyError(err)
  } finally {
    renaming.value = false
  }
}

onMounted(() => {
  void loadSeries()
})
</script>

<template>
  <section class="artifacts-panel">
    <LoadingState v-if="loading" label="正在加载成果…" />

    <div v-else-if="error" class="panel panel--error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">成果加载失败</p>
        <p class="panel--error__desc">{{ error }}</p>
      </div>
      <button type="button" class="btn btn--ghost btn--sm" @click="loadSeries">重试</button>
    </div>

    <EmptyState
      v-else-if="seriesList.length === 0"
      icon="file"
      title="还没有成果"
      description="在该 Task 中执行 Skill 后，产出的 Markdown 成果会出现在这里。"
    />

    <div v-else class="artifacts-layout">
      <aside class="artifacts-sidebar">
        <div v-for="series in seriesList" :key="series.id" class="artifacts-series">
          <button
            type="button"
            class="artifacts-series__head"
            :class="{ 'artifacts-series__head--active': selected?.id === series.id }"
            @click="selectSeries(series.id)"
          >
            <AppIcon name="file" :size="14" />
            <span class="artifacts-series__title">{{ series.title }}</span>
          </button>
          <ul v-if="selected?.id === series.id" class="artifacts-versions">
            <li v-for="artifact in versions" :key="artifact.id">
              <button
                type="button"
                class="artifacts-version"
                :class="{ 'artifacts-version--active': selectedArtifact?.id === artifact.id }"
                @click="selectedArtifact = artifact"
              >
                v{{ artifact.version }}
                <span v-if="series.current_artifact_id === artifact.id" class="chip chip--muted">
                  当前
                </span>
              </button>
            </li>
          </ul>
        </div>
      </aside>

      <article v-if="selectedArtifact" class="artifacts-preview card">
        <header class="artifacts-preview__head">
          <div>
            <h2 class="artifacts-preview__title">{{ selectedArtifact.title }}</h2>
            <p class="artifacts-preview__meta">
              v{{ selectedArtifact.version }}
              <button
                v-if="selectedArtifact.source_message_id"
                type="button"
                class="artifacts-source-link"
                @click="emit('open-source-message', selectedArtifact.source_message_id)"
              >
                查看来源消息
              </button>
              · {{ formatDateTime(selectedArtifact.created_at) }}
            </p>
          </div>
          <div class="artifacts-preview__actions">
            <button type="button" class="btn btn--ghost btn--sm" @click="openRename">
              重命名系列
            </button>
            <button type="button" class="btn btn--ghost btn--sm" @click="downloadCurrent">
              下载
            </button>
            <button
              type="button"
              class="btn btn--ghost btn--sm"
              :disabled="exporting"
              title="复制到 Global Library，之后可被任意 Project 或 Task 引用"
              @click="storeToLibrary"
            >
              {{ exporting ? '存入中…' : '存入 Library' }}
            </button>
            <button
              type="button"
              class="btn btn--ghost btn--sm"
              @click="deleteTarget = selectedArtifact"
            >
              删除
            </button>
          </div>
        </header>
        <MarkdownText :text="selectedArtifact.content ?? ''" />
      </article>

      <p v-else class="artifacts-preview-empty">选择一个版本查看内容。</p>
    </div>

    <Modal
      :open="Boolean(deleteTarget)"
      title="删除成果版本"
      width="420px"
      :dismissible="!deleting"
      @close="deleteTarget = null"
    >
      <p class="artifacts-delete-copy">
        删除「{{ deleteTarget?.title }} v{{ deleteTarget?.version }}」后不可恢复；
        同系列其他版本不受影响。
      </p>
      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="deleting" @click="deleteTarget = null">
          取消
        </button>
        <button type="button" class="btn btn--primary" :disabled="deleting" @click="confirmDeleteArtifact">
          删除
        </button>
      </template>
    </Modal>

    <Modal
      :open="renameOpen"
      title="重命名成果系列"
      width="460px"
      :dismissible="!renaming"
      @close="renameOpen = false"
    >
      <label class="field">
        <span class="field__label">系列标题</span>
        <input v-model="renameDraft" class="input" type="text" maxlength="300" />
      </label>
      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="renaming" @click="renameOpen = false">
          取消
        </button>
        <button type="button" class="btn btn--primary" :disabled="renaming" @click="submitRename">
          保存
        </button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.artifacts-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.artifacts-layout {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.artifacts-sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 8px;
  background: var(--bg-subtle);
}

.artifacts-series__head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 8px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12.5px;
  text-align: left;
  cursor: pointer;
}

.artifacts-series__head:hover,
.artifacts-series__head--active {
  border-color: var(--border);
  background: var(--bg-hover);
  color: var(--text);
}

.artifacts-series__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifacts-versions {
  list-style: none;
  margin: 4px 0 0;
  padding: 0 0 0 20px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.artifacts-version {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 4px 6px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.artifacts-version:hover,
.artifacts-version--active {
  background: var(--bg-hover);
  color: var(--text);
}

.artifacts-preview {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 320px;
}

.artifacts-preview__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.artifacts-preview__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.artifacts-preview__actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.artifacts-delete-copy {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.artifacts-preview__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.artifacts-source-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--accent);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.artifacts-source-link:hover {
  text-decoration: underline;
}

.artifacts-preview-empty {
  padding: 24px;
  color: var(--text-muted);
  font-size: 12.5px;
}

@media (max-width: 900px) {
  .artifacts-layout {
    grid-template-columns: 1fr;
  }
}
</style>
