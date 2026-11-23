import { computed, ref } from 'vue'

import type {
  Execution,
  ExecutionDetail,
  ExecutionStatus,
} from '@/api/types'

export const EXECUTION_STATUS_LABELS: Record<string, string> = {
  pending: '排队中',
  running: '进行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

export const EXECUTION_POLL_INTERVAL_MS = 2000

export function executionStatusLabel(status: string): string {
  return EXECUTION_STATUS_LABELS[status] ?? status
}

export function isExecutionActive(status: string | null | undefined): boolean {
  return status === 'pending' || status === 'running'
}

export function isExecutionTerminal(status: string | null | undefined): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
}

export interface StepLike {
  name: string
  status: string
}

export interface StepProgress {
  total: number
  completed: number
  failed: number
  skipped: number
  running: number
  /** Completed steps as a 0–100 integer (0 when there are no steps yet). */
  percent: number
  /** Name of the step currently running, if any. */
  currentStep: string | null
}

/** Aggregate stage progress for the run card ("阶段进度"). */
export function stepProgress(steps: readonly StepLike[]): StepProgress {
  let completed = 0
  let failed = 0
  let skipped = 0
  let running = 0
  let currentStep: string | null = null
  for (const step of steps) {
    if (step.status === 'completed') completed += 1
    else if (step.status === 'failed') failed += 1
    else if (step.status === 'skipped') skipped += 1
    else if (step.status === 'running') {
      running += 1
      currentStep = step.name
    }
  }
  const total = steps.length
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0
  return { total, completed, failed, skipped, running, percent, currentStep }
}

/** Lightweight step shape carried by execution SSE events. */
export interface ProgressStep {
  id: string
  sequence: number
  step_type: string
  name: string
  status: string
}

export interface ExecutionProgressState {
  status: ExecutionStatus | null
  steps: ProgressStep[]
  skillId: string | null
  skillName: string | null
  modelProvider: string | null
  modelName: string | null
}

export function createExecutionProgressState(): ExecutionProgressState {
  return {
    status: null,
    steps: [],
    skillId: null,
    skillName: null,
    modelProvider: null,
    modelName: null,
  }
}

function asStringOrNull(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null
}

function asStatus(value: unknown): ExecutionStatus | null {
  return value === 'pending' ||
    value === 'running' ||
    value === 'completed' ||
    value === 'failed' ||
    value === 'cancelled'
    ? value
    : null
}

function readStep(value: unknown): ProgressStep | null {
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  if (typeof record.id !== 'string') return null
  return {
    id: record.id,
    sequence: typeof record.sequence === 'number' ? record.sequence : 0,
    step_type: typeof record.step_type === 'string' ? record.step_type : '',
    name: typeof record.name === 'string' ? record.name : '',
    status: typeof record.status === 'string' ? record.status : '',
  }
}

/** Insert or update a step, keeping the list ordered by sequence. */
export function upsertExecutionStep(
  steps: readonly ProgressStep[],
  step: ProgressStep,
): ProgressStep[] {
  const next = steps.map((item) => ({ ...item }))
  const index = next.findIndex((item) => item.id === step.id)
  if (index >= 0) next[index] = step
  else next.push(step)
  return next.sort((a, b) => a.sequence - b.sequence)
}

/**
 * Merge one execution SSE event into the progress state. Pure: the RunProgress
 * poller keeps working, while F6/F10 can reuse this reducer for live events.
 */
export function reduceExecutionEvent(
  state: ExecutionProgressState,
  event: string,
  data: Record<string, unknown>,
): ExecutionProgressState {
  if (event === 'snapshot') {
    const status = asStatus(data.status)
    return {
      ...state,
      status: status ?? state.status,
      modelProvider: asStringOrNull(data.model_provider) ?? state.modelProvider,
      modelName: asStringOrNull(data.model_name) ?? state.modelName,
    }
  }
  if (event === 'execution.started') {
    return {
      ...state,
      status: 'running',
      skillId: asStringOrNull(data.skill_id) ?? state.skillId,
      skillName: asStringOrNull(data.skill_name) ?? state.skillName,
    }
  }
  if (
    event === 'execution.completed' ||
    event === 'execution.failed' ||
    event === 'execution.cancelled'
  ) {
    const status = asStatus(data.status)
    if (status) return { ...state, status }
    const fallback: ExecutionStatus =
      event === 'execution.completed'
        ? 'completed'
        : event === 'execution.failed'
          ? 'failed'
          : 'cancelled'
    return { ...state, status: fallback }
  }
  if (
    event === 'step.started' ||
    event === 'step.completed' ||
    event === 'step.failed' ||
    event === 'step.skipped'
  ) {
    const step = readStep(data.step)
    if (!step) return state
    return { ...state, steps: upsertExecutionStep(state.steps, step) }
  }
  return state
}

export function executionProgressFromDetail(
  detail: ExecutionDetail | null | undefined,
): ExecutionProgressState {
  if (!detail) return createExecutionProgressState()
  return {
    status: detail.status,
    steps: detail.steps.map((step) => ({
      id: step.id,
      sequence: step.sequence,
      step_type: step.step_type,
      name: step.name,
      status: step.status,
    })),
    skillId: detail.skill_id,
    skillName: detail.skill_name,
    modelProvider: detail.model_provider,
    modelName: detail.model_name,
  }
}

export interface ExecutionProgressSource {
  listExecutions: (taskId: string) => Promise<Execution[]>
  getExecution: (executionId: string) => Promise<ExecutionDetail>
}

export interface UseExecutionProgressOptions {
  /** Current task id; read lazily so it can be a reactive prop getter. */
  taskId: () => string
  pollIntervalMs?: number
}

/**
 * RunProgress data layer: initial list/detail load, polling and history
 * selection. UI-only concerns (watchers, mount hooks) stay in the component.
 */
export function useExecutionProgress(
  source: ExecutionProgressSource,
  options: UseExecutionProgressOptions,
) {
  const detail = ref<ExecutionDetail | null>(null)
  const executions = ref<Execution[]>([])
  const loading = ref(true)
  const expanded = ref(false)
  const progressState = ref<ExecutionProgressState>(createExecutionProgressState())
  const progress = computed<StepProgress>(() => stepProgress(progressState.value.steps))

  let timer: ReturnType<typeof setInterval> | null = null
  const pollIntervalMs = options.pollIntervalMs ?? EXECUTION_POLL_INTERVAL_MS

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
    }, pollIntervalMs)
  }

  function applyDetail(next: ExecutionDetail): void {
    detail.value = next
    progressState.value = executionProgressFromDetail(next)
  }

  async function refresh(): Promise<void> {
    const current = detail.value
    if (!current) return
    try {
      const next = await source.getExecution(current.id)
      applyDetail(next)
      if (isExecutionTerminal(next.status)) {
        stopPolling()
        if (next.status === 'failed') expanded.value = true
        void source
          .listExecutions(current.task_id)
          .then((items) => {
            executions.value = items
          })
          .catch(() => undefined)
      }
    } catch {
      stopPolling()
    }
  }

  async function select(item: Execution): Promise<void> {
    try {
      applyDetail(await source.getExecution(item.id))
      if (isExecutionActive(detail.value?.status)) startPolling()
      else stopPolling()
    } catch {
      /* ignore */
    }
  }

  async function load(): Promise<void> {
    loading.value = true
    try {
      const items = await source.listExecutions(options.taskId())
      executions.value = items
      if (items.length === 0) {
        detail.value = null
        progressState.value = createExecutionProgressState()
        stopPolling()
        return
      }
      applyDetail(await source.getExecution(items[0].id))
      if (isExecutionActive(detail.value?.status)) startPolling()
      else stopPolling()
    } catch {
      detail.value = null
      progressState.value = createExecutionProgressState()
    } finally {
      loading.value = false
    }
  }

  /** Merge a live execution event (used by future streaming run cards). */
  function applyEvent(event: string, data: Record<string, unknown>): void {
    progressState.value = reduceExecutionEvent(progressState.value, event, data)
  }

  return {
    detail,
    executions,
    loading,
    expanded,
    progress,
    progressState,
    load,
    refresh,
    select,
    startPolling,
    stopPolling,
    applyEvent,
  }
}
