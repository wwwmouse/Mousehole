<script setup lang="ts">
import { onMounted, ref } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import {
  getTaskFiles,
  removeTaskFileOverride,
  updateTaskFile,
  uploadFile,
} from '@/api/endpoints'
import type { TaskAvailableFile } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'

const props = defineProps<{ taskId: string }>()
const emit = defineEmits<{ 'switch-settings': []; 'files-changed': [] }>()

const app = useAppStore()

const extraFiles = ref<TaskAvailableFile[]>([])
const inheritedCount = ref(0)
const excludedCount = ref(0)
const loading = ref(true)
const uploading = ref(false)
const error = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const context = await getTaskFiles(props.taskId)
    extraFiles.value = context.available.filter(
      (item) => item.source !== 'project' && item.source !== 'project_inherited',
    )
    inheritedCount.value = context.available.filter(
      (item) => item.source === 'project' || item.source === 'project_inherited',
    ).length
    excludedCount.value = context.excluded.length
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
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
  uploading.value = true
  error.value = null
  try {
    const uploaded = await uploadFile(file)
    await updateTaskFile(props.taskId, {
      file_id: uploaded.id,
      action: 'include',
    })
    app.notify('success', `已临时引用「${uploaded.filename}」`)
    await load()
    emit('files-changed')
  } catch (err) {
    error.value = errorMessage(err)
    app.notifyError(err)
  } finally {
    uploading.value = false
  }
}

async function removeExtra(item: TaskAvailableFile): Promise<void> {
  try {
    await removeTaskFileOverride(props.taskId, item.file.id)
    app.notify('success', `已移除临时引用「${item.file.filename}」`)
    await load()
    emit('files-changed')
  } catch (err) {
    app.notifyError(err)
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="side-panel">
    <header class="side-panel__head">
      <h3 class="side-panel__title">临时文件</h3>
      <button
        type="button"
        class="btn btn--ghost btn--sm"
        :disabled="uploading"
        @click="pickFile"
      >
        <span v-if="uploading" class="spinner spinner--sm" aria-hidden="true" />
        <AppIcon v-else name="upload" :size="13" />
        添加
      </button>
      <input
        ref="fileInput"
        class="hidden-input"
        type="file"
        accept=".pdf,.md,.markdown,.txt"
        @change="onFileSelected"
      />
    </header>
    <p class="side-panel__hint">只加入当前 Task，不修改 Project 文件。</p>

    <p v-if="loading" class="side-panel__muted">加载中…</p>
    <p v-else-if="error" class="side-panel__error">{{ error }}</p>

    <ul v-else-if="extraFiles.length" class="side-list">
      <li v-for="item in extraFiles" :key="item.file.id" class="side-list__item">
        <span class="side-list__name" :title="item.file.filename">{{ item.file.filename }}</span>
        <button
          type="button"
          class="side-list__remove"
          title="移除临时引用"
          @click="removeExtra(item)"
        >
          <AppIcon name="close" :size="12" />
        </button>
      </li>
    </ul>
    <p v-else class="side-panel__muted">暂无临时引用文件。</p>

    <p class="side-panel__counts">
      项目继承 {{ inheritedCount }} · 已排除 {{ excludedCount }}
    </p>
    <button
      type="button"
      class="side-panel__link"
      @click="emit('switch-settings')"
    >
      管理完整上下文 →
    </button>
  </section>
</template>

<style scoped>
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-subtle);
}

.side-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.side-panel__title {
  margin: 0;
  font-size: 12.5px;
  font-weight: 600;
}

.side-panel__hint {
  margin: 0;
  font-size: 11px;
  color: var(--text-faint);
}

.side-panel__muted {
  margin: 0;
  font-size: 11.5px;
  color: var(--text-muted);
}

.side-panel__error {
  margin: 0;
  font-size: 11.5px;
  color: var(--danger);
}

.side-panel__counts {
  margin: 0;
  font-size: 11px;
  color: var(--text-faint);
}

.side-panel__link {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 11.5px;
  cursor: pointer;
}

.side-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 160px;
  overflow-y: auto;
}

.side-list__item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
}

.side-list__name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}

.side-list__remove {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-faint);
  cursor: pointer;
}

.side-list__remove:hover {
  background: var(--bg-hover);
  color: var(--danger);
}

.hidden-input {
  display: none;
}
</style>
