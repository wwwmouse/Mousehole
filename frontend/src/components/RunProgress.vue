<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import { getExecution, listExecutions } from '@/api/endpoints'
import type { ExecutionDetail } from '@/api/types'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ taskId: string; refreshKey?: number }>()

const detail = ref<ExecutionDetail | null>(null)
const loading = ref(true)
const expanded = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const STATUS_LABELS: Record<string, string> = {
  pending: '排队中',
  running: '进行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

const statusLabel = computed(() =>
  detail.value ? (STATUS_LABELS[detail.value.status] ?? detail.value.status) : '',
)
const isActive = computed(() =>
  detail.value
    ? detail.value.status === 'pending' || detail.value.status === 'running'
    : false,
)

function stopPolling(): void {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function startPolling(): void {
  stopPolling()
  timer = setInterval(() => {
    void refresh()
  }, 2000)
}

async function refresh(): Promise<void> {
  const current = detail.value
  if (!current) return
  try {
    const next = await getExecution(current.id)
    detail.value = next
    if (next.status === 'completed' || next.status === 'failed' || next.status === 'cancelled') {
      stopPolling()
      if (next.status === 'failed') expanded.value = true
    }
  } catch {
    stopPolling()
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const executions = await listExecutions(props.taskId)
    if (executions.length === 0) {
      detail.value = null
      stopPolling()
      return
    }
    detail.value = await getExecution(executions[0].id)
    if (isActive.value) startPolling()
    else stopPolling()
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => props.refreshKey,
  () => {
    void load()
  },
)
watch(
  () => props.taskId,
  () => {
    void load()
  },
)

onMounted(() => {
  void load()
})

onBeforeUnmount(stopPolling)
</script>

<template>
  <section v-if="detail" class="run-progress">
    <button
      type="button"
      class="run-progress__head"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <span
        class="run-progress__dot"
        :class="`run-progress__dot--${detail.status}`"
        aria-hidden="true"
      />
      <span class="run-progress__title">工作进度</span>
      <span v-if="detail.skill_name" class="run-progress__skill">{{ detail.skill_name }}</span>
      <span class="chip" :class="`chip--status-${detail.status}`">{{ statusLabel }}</span>
      <span class="run-progress__time">{{ formatDateTime(detail.created_at) }}</span>
      <AppIcon
        class="run-progress__chevron"
        :class="{ 'run-progress__chevron--open': expanded }"
        name="chevron-down"
        :size="13"
      />
    </button>

    <div v-if="expanded" class="run-progress__body">
      <ul v-if="detail.steps.length" class="run-progress__steps">
        <li
          v-for="step in detail.steps"
          :key="step.id"
          class="run-progress__step"
          :class="`run-progress__step--${step.status}`"
        >
          <span class="run-progress__step-dot" aria-hidden="true" />
          <span>{{ step.name }}</span>
          <span class="run-progress__step-status">{{ step.status }}</span>
        </li>
      </ul>
      <ul v-if="detail.snapshots.length" class="run-progress__files">
        <li v-for="snapshot in detail.snapshots" :key="snapshot.id" class="run-progress__file">
          <AppIcon name="file" :size="11" />
          <span class="run-progress__file-name">{{ snapshot.filename_snapshot }}</span>
          <span class="chip chip--muted">
            {{ snapshot.usage_mode === 'direct' ? '直接使用' : '已摘要' }}
          </span>
        </li>
      </ul>
      <p class="run-progress__meta">
        <template v-if="detail.model_name">{{ detail.model_provider }} / {{ detail.model_name }}</template>
        <template v-if="detail.usage?.total_tokens"> · {{ detail.usage.total_tokens }} tokens</template>
        <template v-if="detail.snapshots.length">
          · 使用 {{ detail.snapshots.length }} 个文件（直接
          {{ detail.snapshots.filter((item) => item.usage_mode === 'direct').length }} / 摘要
          {{ detail.snapshots.filter((item) => item.usage_mode === 'summarized').length }}）
        </template>
      </p>
      <p v-if="detail.error_message" class="run-progress__error">{{ detail.error_message }}</p>
    </div>
  </section>
</template>

<style scoped>
.run-progress {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  overflow: hidden;
}

.run-progress__head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.run-progress__head:hover {
  background: var(--bg-hover);
}

.run-progress__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-faint);
}

.run-progress__dot--running,
.run-progress__dot--pending {
  background: var(--accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 18%, transparent);
}

.run-progress__dot--completed {
  background: var(--success);
}

.run-progress__dot--failed {
  background: var(--danger);
}

.run-progress__dot--cancelled {
  background: var(--warning);
}

.run-progress__title {
  font-weight: 600;
  color: var(--text);
}

.run-progress__skill {
  color: var(--text-muted);
}

.run-progress__time {
  margin-left: auto;
  font-size: 10.5px;
  color: var(--text-faint);
}

.run-progress__chevron {
  color: var(--text-faint);
  transition: transform 0.15s ease;
}

.run-progress__chevron--open {
  transform: rotate(180deg);
}

.run-progress__body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 12px 10px;
  border-top: 1px solid var(--border);
}

.run-progress__steps {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.run-progress__step {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11.5px;
  color: var(--text-secondary);
}

.run-progress__step-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-faint);
}

.run-progress__step--completed .run-progress__step-dot {
  background: var(--success);
}

.run-progress__step--running .run-progress__step-dot {
  background: var(--accent);
}

.run-progress__step--failed .run-progress__step-dot {
  background: var(--danger);
}

.run-progress__step-status {
  margin-left: auto;
  font-size: 10.5px;
  color: var(--text-faint);
}

.run-progress__files {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.run-progress__file {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-secondary);
}

.run-progress__file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-progress__meta {
  margin: 0;
  font-size: 10.5px;
  color: var(--text-faint);
}

.run-progress__error {
  margin: 0;
  font-size: 11.5px;
  color: var(--danger);
}
</style>
