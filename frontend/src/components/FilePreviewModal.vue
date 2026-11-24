<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import MarkdownText from '@/components/MarkdownText.vue'
import Modal from '@/components/Modal.vue'
import { fileRawUrl, getFile, getFileContent } from '@/api/endpoints'
import type { FileContent, FileDetail } from '@/api/types'
import { errorMessage } from '@/utils/errors'
import { fileTypeLabel, formatBytes, formatDateTime } from '@/utils/format'

const props = defineProps<{ fileId: string | null }>()
const emit = defineEmits<{ close: [] }>()

const detail = ref<FileDetail | null>(null)
const content = ref<FileContent | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const isOpen = computed(() => Boolean(props.fileId))
const isPdf = computed(() => detail.value?.file_type === 'pdf')
const rawUrl = computed(() =>
  props.fileId ? fileRawUrl(props.fileId) : '',
)
const isMarkdown = computed(() => {
  const type = detail.value?.file_type
  return type === 'md' || type === 'markdown'
})

async function load(fileId: string): Promise<void> {
  loading.value = true
  error.value = null
  detail.value = null
  content.value = null
  try {
    const fileDetail = await getFile(fileId)
    detail.value = fileDetail
    // PDF 用浏览器原生预览，避免扫描版/复杂排版被纯文本提取后看起来一片空白。
    if (fileDetail.file_type !== 'pdf') {
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
    if (value) void load(value)
  },
  { immediate: true },
)
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
      <div class="preview-body">
        <iframe
          v-if="isPdf"
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
