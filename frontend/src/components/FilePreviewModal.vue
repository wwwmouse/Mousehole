<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import MarkdownText from '@/components/MarkdownText.vue'
import Modal from '@/components/Modal.vue'
import {
  fileRawUrl,
  getFile,
  getFileContent,
  getFileOcr,
  startFileOcr,
} from '@/api/endpoints'
import type { FileContent, FileDetail, OcrJob } from '@/api/types'
import { errorMessage } from '@/utils/errors'
import { fileTypeLabel, formatBytes, formatDateTime } from '@/utils/format'

const props = defineProps<{ fileId: string | null; page?: number }>()
const emit = defineEmits<{ close: [] }>()

const detail = ref<FileDetail | null>(null)
const content = ref<FileContent | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const ocrJob = ref<OcrJob | null>(null)
const ocrBusy = ref(false)
const ocrError = ref<string | null>(null)
const pdfTab = ref<'preview' | 'text'>('preview')
let pollTimer: number | null = null

const isOpen = computed(() => Boolean(props.fileId))
const isPdf = computed(() => detail.value?.file_type === 'pdf')
const rawUrl = computed(() =>
  props.fileId ? fileRawUrl(props.fileId, props.page) : '',
)
const isMarkdown = computed(() => {
  const type = detail.value?.file_type
  return type === 'md' || type === 'markdown'
})
const ocrDone = computed(() => ocrJob.value?.status === 'completed')

function stopPolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

async function loadText(fileId: string): Promise<void> {
  try {
    content.value = await getFileContent(fileId)
  } catch (err) {
    // PDF 页文本尚未就绪时不覆盖原始页面预览。
    content.value = null
    if (!ocrDone.value) ocrError.value = errorMessage(err)
  }
}

function startPolling(fileId: string): void {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    try {
      const job = await getFileOcr(fileId)
      ocrJob.value = job
      if (!job || job.status === 'completed') {
        stopPolling()
        if (job) await loadText(fileId)
      } else if (job.status === 'failed') {
        stopPolling()
      }
    } catch {
      stopPolling()
    }
  }, 1000)
}

async function startOcr(): Promise<void> {
  if (!props.fileId || ocrBusy.value) return
  ocrBusy.value = true
  ocrError.value = null
  try {
    ocrJob.value = await startFileOcr(props.fileId)
    pdfTab.value = 'preview'
    startPolling(props.fileId)
  } catch (err) {
    ocrError.value = errorMessage(err)
  } finally {
    ocrBusy.value = false
  }
}

async function load(fileId: string): Promise<void> {
  stopPolling()
  loading.value = true
  error.value = null
  detail.value = null
  content.value = null
  ocrJob.value = null
  ocrError.value = null
  pdfTab.value = 'preview'
  try {
    const fileDetail = await getFile(fileId)
    detail.value = fileDetail
    if (fileDetail.file_type === 'pdf') {
      ocrJob.value = await getFileOcr(fileId)
      if (ocrJob.value?.status === 'completed') {
        await loadText(fileId)
      } else if (
        ocrJob.value?.status === 'pending' ||
        ocrJob.value?.status === 'running'
      ) {
        startPolling(fileId)
      }
    } else {
      content.value = await getFileContent(fileId)
    }
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

watch(
  () => props.fileId,
  (value) => {
    if (value) {
      void load(value)
    } else {
      stopPolling()
    }
  },
  { immediate: true },
)

onBeforeUnmount(stopPolling)
</script>

<template>
  <Modal
    :open="isOpen"
    :title="detail?.filename ?? '文件预览'"
    width="880px"
    :z-index="200"
    @close="emit('close')"
  >
    <div v-if="loading" class="preview-loading">
      <span class="spinner spinner--sm" aria-hidden="true" />
      正在读取文件内容…
    </div>

    <div v-else-if="error" class="panel panel--error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">文件读取失败</p>
        <p class="panel--error__desc">{{ error }}</p>
      </div>
    </div>

    <template v-else-if="detail">
      <div class="preview-meta">
        <span class="chip">{{ fileTypeLabel(detail.file_type) }}</span>
        <span>{{ formatBytes(detail.size) }}</span>
        <span>更新于 {{ formatDateTime(detail.updated_at) }}</span>
        <span v-if="content?.truncated" class="preview-meta__warn">内容已截断</span>
      </div>

      <div v-if="isPdf" class="ocr-bar">
        <template v-if="!ocrJob">
          <span class="ocr-bar__text">
            扫描版 PDF 可先做页面识别；文本型 PDF 会直接读取文字层。
          </span>
          <button
            type="button"
            class="btn btn--primary btn--sm"
            :disabled="ocrBusy"
            @click="startOcr"
          >
            {{ ocrBusy ? '启动中…' : '开始 OCR / 解析页面' }}
          </button>
        </template>
        <template v-else-if="ocrJob.status === 'pending' || ocrJob.status === 'running'">
          <span class="ocr-bar__text">
            正在读取第 {{ ocrJob.current_page ?? Math.min(ocrJob.processed_pages + 1, ocrJob.total_pages) }} 页…
          </span>
          <span class="ocr-bar__progress">
            {{ ocrJob.processed_pages }} / {{ ocrJob.total_pages }}
          </span>
        </template>
        <template v-else-if="ocrJob.status === 'completed'">
          <span class="ocr-bar__text">
            已解析 {{ ocrJob.processed_pages }} 页：文本页 {{ ocrJob.native_pages }} ·
            OCR 页 {{ ocrJob.ocr_pages }} · 平均图片覆盖率 {{ ocrJob.image_coverage }}%
          </span>
          <div class="ocr-bar__tabs">
            <button
              type="button"
              class="btn btn--ghost btn--sm"
              :class="{ 'btn--active': pdfTab === 'preview' }"
              @click="pdfTab = 'preview'"
            >
              原始页面
            </button>
            <button
              type="button"
              class="btn btn--ghost btn--sm"
              :class="{ 'btn--active': pdfTab === 'text' }"
              @click="pdfTab = 'text'"
            >
              文字
            </button>
          </div>
        </template>
        <template v-else-if="ocrJob.status === 'failed'">
          <span class="ocr-bar__text ocr-bar__text--error">
            页面识别失败：{{ ocrJob.error || '未知错误' }}
          </span>
          <button
            type="button"
            class="btn btn--ghost btn--sm"
            :disabled="ocrBusy"
            @click="startOcr"
          >
            重试
          </button>
        </template>
        <span v-if="ocrError" class="ocr-bar__text ocr-bar__text--error">
          {{ ocrError }}
        </span>
      </div>

      <div class="preview-body">
        <iframe
          v-if="isPdf && pdfTab === 'preview'"
          :src="rawUrl"
          class="preview-pdf"
          title="PDF 原始页面预览"
        />
        <MarkdownText v-else-if="isMarkdown && content" :text="content.text" />
        <pre v-else-if="content" class="preview-text">{{ content.text }}</pre>
        <p v-else class="preview-empty">没有可显示的内容。</p>
      </div>
    </template>
  </Modal>
</template>

<style scoped>
.preview-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 24px;
  color: var(--text-muted);
  font-size: 12.5px;
}

.preview-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-faint);
}

.preview-meta__warn {
  color: var(--warning);
}

.ocr-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  padding: 9px 10px;
  margin-bottom: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  font-size: 12px;
  color: var(--text-muted);
}

.ocr-bar__text {
  line-height: 1.5;
}

.ocr-bar__text--error {
  color: var(--danger);
}

.ocr-bar__progress {
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

.ocr-bar__tabs {
  display: flex;
  gap: 4px;
}

.ocr-bar__tabs .btn--active {
  border-color: var(--accent);
  color: var(--accent);
}

.preview-body {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}

.preview-pdf {
  width: 100%;
  height: 60vh;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: #fff;
}

.preview-text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.preview-empty {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-muted);
}
</style>
