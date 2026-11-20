<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import LoadingState from '@/components/LoadingState.vue'
import {
  cancelExecution,
  createExecution,
  getExecution,
  listExecutions,
} from '@/api/endpoints'
import { streamExecutionEvents } from '@/api/execution'
import type { Execution, ExecutionDetail } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ taskId: string; hasModel: boolean }>()
const emit = defineEmits<{ 'open-artifacts': []; 'execution-changed': [] }>()

const app = useAppStore()

const executions = ref<Execution[]>([])
const active = ref<ExecutionDetail | null>(null)
const loading = ref(true)
const starting = ref(false)
const cancelling = ref(false)
const error = ref<string | null>(null)

const runningId = ref<string | null>(null)
const liveStatus = ref<string>('')
const liveSteps = ref<{ step_type: string; name: string; status: string }[]>([])
let abort: AbortController | null = null

const latest = computed(() => executions.value[0] ?? null)
const isRunning = computed(() => runningId.value !== null)

const STATUS_LABELS: Record<string, string> = {
  pending: '排队中',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status
}

async function loadList(): Promise<void> {
  try {
    executions.value = await listExecutions(props.taskId)
    if (active.value) await loadDetail(active.value.id)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function loadDetail(executionId: string): Promise<void> {
  try {
    active.value = await getExecution(executionId)
  } catch (err) {
    error.value = errorMessage(err)
  }
}

async function start(): Promise<void> {
  if (!props.hasModel) {
    error.value =
      '尚未配置可用模型：请先在 Settings 配置 DeepSeek API Key 或启用 Ollama。'
    return
  }
  starting.value = true
  error.value = null
  liveSteps.value = []
  try {
    const execution = await createExecution(props.taskId)
    executions.value = [execution, ...executions.value]
    await track(execution)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    starting.value = false
  }
}

async function track(execution: Execution): Promise<void> {
  runningId.value = execution.id
  liveStatus.value = execution.status
  abort = new AbortController()
  try {
    await streamExecutionEvents(
      execution.id,
      {
        onEvent: (event, data) => {
          if (event === 'snapshot') {
            liveStatus.value = String(data.status ?? '')
          } else if (event.startsWith('step.')) {
            const step = data.step as
              | { step_type?: string; name?: string; status?: string }
              | undefined
            if (step?.step_type) {
              const index = liveSteps.value.findIndex(
                (item) => item.step_type === step.step_type,
              )
              const next = {
                step_type: step.step_type,
                name: step.name ?? step.step_type,
                status: step.status ?? 'running',
              }
              if (index >= 0) liveSteps.value[index] = next
              else liveSteps.value.push(next)
            }
          } else if (event === 'execution.completed') {
            liveStatus.value = 'completed'
          } else if (event === 'execution.failed') {
            liveStatus.value = 'failed'
            error.value = String(data.error_code ?? 'execution_failed')
          } else if (event === 'execution.cancelled') {
            liveStatus.value = 'cancelled'
          }
        },
      },
      abort.signal,
    )
  } catch (err) {
    if (!(err instanceof DOMException && err.name === 'AbortError')) {
      error.value = errorMessage(err)
    }
  } finally {
    runningId.value = null
    abort = null
    await loadList()
    if (liveStatus.value === 'completed') {
      app.notify('success', '分析完成，报告已生成')
      emit('open-artifacts')
    } else if (liveStatus.value === 'cancelled') {
      app.notify('info', '执行已取消')
    }
    emit('execution-changed')
  }
}

async function cancel(): Promise<void> {
  const id = runningId.value
  if (!id) return
  cancelling.value = true
  try {
    await cancelExecution(id)
    app.notify('info', '已请求取消，将在安全检查点停止')
  } catch (err) {
    app.notifyError(err)
  } finally {
    cancelling.value = false
  }
}

function selectExecution(execution: Execution): void {
  if (execution.status === 'pending' || execution.status === 'running') return
  void loadDetail(execution.id)
}

onMounted(() => {
  void loadList()
})
</script>

<template>
  <section class="card execution-panel">
    <header class="execution-panel__head">
      <div>
        <h2 class="execution-panel__title">多文档分析</h2>
        <p class="execution-panel__desc">
          使用当前 Task 的可用文件发起一次可追溯的 Execution，产出 Markdown 报告。
        </p>
      </div>
      <div class="execution-panel__actions">
        <button
          v-if="isRunning"
          type="button"
          class="btn btn--ghost btn--sm"
          :disabled="cancelling"
          @click="cancel"
        >
          停止
        </button>
        <button
          v-else
          type="button"
          class="btn btn--primary btn--sm"
          :disabled="starting || !hasModel"
          @click="start"
        >
          <span v-if="starting" class="spinner spinner--sm" aria-hidden="true" />
          <AppIcon v-else name="sparkles" :size="14" />
          发起分析
        </button>
      </div>
    </header>

    <div v-if="error" class="panel panel--error execution-panel__error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">执行失败</p>
        <p class="panel--error__desc">{{ error }}</p>
      </div>
      <button type="button" class="btn btn--ghost btn--sm" @click="error = null">关闭</button>
    </div>

    <div v-if="isRunning" class="execution-live">
      <p class="execution-live__status">
        <span class="spinner spinner--sm" aria-hidden="true" />
        {{ statusLabel(liveStatus || 'running') }}
      </p>
      <ul class="execution-steps">
        <li v-for="step in liveSteps" :key="step.step_type" class="execution-step">
          <span
            class="execution-step__dot"
            :class="`execution-step__dot--${step.status}`"
            aria-hidden="true"
          />
          <span class="execution-step__name">{{ step.name }}</span>
          <span class="execution-step__status">{{ step.status }}</span>
        </li>
      </ul>
    </div>

    <LoadingState v-else-if="loading" compact label="正在加载执行历史…" />

    <p v-else-if="!latest" class="execution-empty">还没有执行记录。点击「发起分析」开始。</p>

    <div v-else class="execution-history">
      <div class="execution-latest">
        <span class="chip" :class="`chip--status-${latest.status}`">
          {{ statusLabel(latest.status) }}
        </span>
        <span class="execution-latest__meta">
          #{{ latest.sequence }} · {{ latest.model_provider }} / {{ latest.model_name }}
        </span>
        <span v-if="latest.usage?.total_tokens" class="execution-latest__meta">
          {{ latest.usage.total_tokens }} tokens
        </span>
        <button
          v-if="latest.status === 'completed'"
          type="button"
          class="btn btn--ghost btn--sm execution-latest__link"
          @click="emit('open-artifacts')"
        >
          查看成果
        </button>
      </div>

      <ul class="execution-list">
        <li v-for="item in executions" :key="item.id">
          <button
            type="button"
            class="execution-row"
            :class="{ 'execution-row--active': active?.id === item.id }"
            @click="selectExecution(item)"
          >
            <span class="execution-row__seq">#{{ item.sequence }}</span>
            <span class="execution-row__status" :class="`execution-row__status--${item.status}`">
              {{ statusLabel(item.status) }}
            </span>
            <span class="execution-row__meta">
              {{ formatDateTime(item.created_at) }}
            </span>
          </button>
        </li>
      </ul>

      <div v-if="active" class="execution-detail">
        <h3 class="execution-detail__title">Execution #{{ active.sequence }} 详情</h3>
        <div v-if="active.steps.length" class="execution-detail__section">
          <span class="execution-detail__label">关键步骤</span>
          <ul class="execution-steps">
            <li v-for="step in active.steps" :key="step.id" class="execution-step">
              <span class="execution-step__dot" :class="`execution-step__dot--${step.status}`" />
              <span class="execution-step__name">{{ step.name }}</span>
              <span class="execution-step__status">{{ step.status }}</span>
            </li>
          </ul>
        </div>
        <div v-if="active.snapshots.length" class="execution-detail__section">
          <span class="execution-detail__label">实际使用的文件</span>
          <ul class="execution-snapshots">
            <li v-for="snapshot in active.snapshots" :key="snapshot.id">
              {{ snapshot.filename_snapshot }}
              <span class="chip chip--muted">{{ snapshot.usage_mode === 'direct' ? '直接使用' : '已摘要' }}</span>
            </li>
          </ul>
        </div>
        <p v-if="active.error_message" class="execution-detail__error">
          {{ active.error_message }}
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.execution-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.execution-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.execution-panel__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.execution-panel__desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.execution-live__status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
  font-size: 12.5px;
  color: var(--text-secondary);
}

.execution-steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.execution-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}

.execution-step__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-faint);
}

.execution-step__dot--completed {
  background: var(--success);
}

.execution-step__dot--running {
  background: var(--accent);
}

.execution-step__dot--failed {
  background: var(--danger);
}

.execution-step__dot--skipped {
  background: var(--warning);
}

.execution-step__name {
  color: var(--text-secondary);
}

.execution-step__status {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-faint);
}

.execution-latest {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.execution-latest__meta {
  font-size: 11.5px;
  color: var(--text-muted);
}

.execution-latest__link {
  margin-left: auto;
}

.execution-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 200px;
  overflow-y: auto;
}

.execution-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 9px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.execution-row:hover,
.execution-row--active {
  border-color: var(--border);
  background: var(--bg-hover);
}

.execution-row__seq {
  font-family: var(--font-mono);
  color: var(--text-faint);
}

.execution-row__status--completed {
  color: var(--success);
}

.execution-row__status--failed {
  color: var(--danger);
}

.execution-row__status--cancelled {
  color: var(--warning);
}

.execution-row__meta {
  margin-left: auto;
  color: var(--text-faint);
}

.execution-detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}

.execution-detail__title {
  margin: 0;
  font-size: 12.5px;
  font-weight: 600;
}

.execution-detail__section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.execution-detail__label {
  font-size: 11px;
  color: var(--text-faint);
}

.execution-snapshots {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
}

.execution-snapshots li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.execution-detail__error {
  margin: 0;
  font-size: 12px;
  color: var(--danger);
}

.execution-empty {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-muted);
}
</style>
