import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ExecutionDetail, ExecutionStatus } from '@/api/types'
import {
  createExecutionProgressState,
  executionProgressFromDetail,
  executionStatusLabel,
  isExecutionActive,
  isExecutionTerminal,
  reduceExecutionEvent,
  stepProgress,
  upsertExecutionStep,
  useExecutionProgress,
  type ExecutionProgressState,
  type ProgressStep,
} from '@/composables/useExecutionProgress'
import {
  makeExecution,
  makeExecutionDetail,
  makeStep,
} from './factories'

function step(overrides: Partial<ProgressStep> = {}): ProgressStep {
  return {
    id: 'step-1',
    sequence: 1,
    step_type: 'resolve_files',
    name: '解析可用文件',
    status: 'running',
    ...overrides,
  }
}

function eventStep(overrides: Partial<Record<string, unknown>> = {}) {
  return { id: 'step-1', sequence: 1, step_type: 'resolve_files', name: '解析可用文件', ...overrides }
}

function applyEvents(
  events: Array<[string, Record<string, unknown>]>,
): ExecutionProgressState {
  return events.reduce(
    (state, [name, data]) => reduceExecutionEvent(state, name, data),
    createExecutionProgressState(),
  )
}

afterEach(() => {
  vi.useRealTimers()
})

describe('execution status helpers', () => {
  it('maps every backend status to a Chinese label', () => {
    expect(executionStatusLabel('pending')).toBe('排队中')
    expect(executionStatusLabel('running')).toBe('进行中')
    expect(executionStatusLabel('completed')).toBe('已完成')
    expect(executionStatusLabel('failed')).toBe('失败')
    expect(executionStatusLabel('cancelled')).toBe('已取消')
    expect(executionStatusLabel('weird')).toBe('weird')
  })

  it('detects active and terminal statuses', () => {
    expect(isExecutionActive('pending')).toBe(true)
    expect(isExecutionActive('running')).toBe(true)
    expect(isExecutionActive('completed')).toBe(false)
    expect(isExecutionActive(null)).toBe(false)
    expect(isExecutionTerminal('completed')).toBe(true)
    expect(isExecutionTerminal('failed')).toBe(true)
    expect(isExecutionTerminal('cancelled')).toBe(true)
    expect(isExecutionTerminal('running')).toBe(false)
  })
})

describe('stepProgress', () => {
  it('returns zeroed progress for no steps', () => {
    expect(stepProgress([])).toEqual({
      total: 0,
      completed: 0,
      failed: 0,
      skipped: 0,
      running: 0,
      percent: 0,
      currentStep: null,
    })
  })

  it('aggregates completed / failed / skipped / running steps', () => {
    const progress = stepProgress([
      { name: '解析', status: 'completed' },
      { name: '读取', status: 'completed' },
      { name: '生成', status: 'running' },
      { name: '保存', status: 'failed' },
      { name: '收尾', status: 'skipped' },
    ])
    expect(progress).toEqual({
      total: 5,
      completed: 2,
      failed: 1,
      skipped: 1,
      running: 1,
      percent: 40,
      currentStep: '生成',
    })
  })

  it('rounds the completion percentage', () => {
    expect(
      stepProgress([
        { name: 'a', status: 'completed' },
        { name: 'b', status: 'running' },
        { name: 'c', status: 'pending' },
      ]).percent,
    ).toBe(33)
  })
})

describe('upsertExecutionStep', () => {
  it('inserts steps ordered by sequence', () => {
    const steps = upsertExecutionStep(
      [step({ id: 's2', sequence: 2 })],
      step({ id: 's1', sequence: 1 }),
    )
    expect(steps.map((item) => item.id)).toEqual(['s1', 's2'])
  })

  it('updates an existing step in place', () => {
    const steps = upsertExecutionStep(
      [step({ id: 's1', status: 'running' })],
      step({ id: 's1', status: 'completed' }),
    )
    expect(steps).toHaveLength(1)
    expect(steps[0].status).toBe('completed')
  })
})

describe('reduceExecutionEvent', () => {
  it('stores status / model info from the snapshot event', () => {
    const state = applyEvents([
      [
        'snapshot',
        { status: 'running', model_provider: 'deepseek', model_name: 'deepseek-chat' },
      ],
    ])
    expect(state.status).toBe('running')
    expect(state.modelProvider).toBe('deepseek')
    expect(state.modelName).toBe('deepseek-chat')
  })

  it('marks the execution running with skill info on execution.started', () => {
    const state = applyEvents([
      ['execution.started', { status: 'running', skill_id: 'skill-1', skill_name: '总结' }],
    ])
    expect(state.status).toBe('running')
    expect(state.skillId).toBe('skill-1')
    expect(state.skillName).toBe('总结')
  })

  it('falls back to the event name when terminal payloads omit status', () => {
    expect(applyEvents([['execution.completed', {}]]).status).toBe('completed')
    expect(applyEvents([['execution.failed', {}]]).status).toBe('failed')
    expect(applyEvents([['execution.cancelled', {}]]).status).toBe('cancelled')
  })

  it('adds a step on step.started and updates it on step.completed', () => {
    const state = applyEvents([
      ['step.started', { step: eventStep({ status: 'running' }) }],
      [
        'step.completed',
        { step: eventStep({ status: 'completed', name: '解析可用文件' }) },
      ],
    ])
    expect(state.steps).toEqual([
      {
        id: 'step-1',
        sequence: 1,
        step_type: 'resolve_files',
        name: '解析可用文件',
        status: 'completed',
      },
    ])
  })

  it('keeps step order when events arrive out of order', () => {
    const state = applyEvents([
      ['step.started', { step: eventStep({ id: 's2', sequence: 2, status: 'running' }) }],
      ['step.started', { step: eventStep({ id: 's1', sequence: 1, status: 'completed' }) }],
    ])
    expect(state.steps.map((item) => item.id)).toEqual(['s1', 's2'])
  })

  it('ignores malformed steps and unknown events', () => {
    const state = createExecutionProgressState()
    expect(reduceExecutionEvent(state, 'step.started', {})).toBe(state)
    expect(reduceExecutionEvent(state, 'step.started', { step: { name: 'x' } })).toBe(state)
    expect(reduceExecutionEvent(state, 'nope', { status: 'running' })).toBe(state)
  })
})

describe('executionProgressFromDetail', () => {
  it('maps a detail payload into progress state', () => {
    const detail = makeExecutionDetail({
      status: 'failed',
      model_provider: 'ollama',
      model_name: 'qwen',
      skill_id: 'skill-1',
      skill_name: '总结',
      steps: [
        makeStep({ id: 's1', sequence: 1, status: 'completed' }),
        makeStep({ id: 's2', sequence: 2, status: 'failed' }),
      ],
    })
    const state = executionProgressFromDetail(detail)
    expect(state.status).toBe('failed')
    expect(state.steps).toHaveLength(2)
    expect(state.steps[1]).toMatchObject({ id: 's2', status: 'failed' })
    expect(state.skillName).toBe('总结')
    expect(state.modelProvider).toBe('ollama')
  })

  it('returns empty state for null detail', () => {
    expect(executionProgressFromDetail(null)).toEqual(createExecutionProgressState())
  })
})

describe('useExecutionProgress', () => {
  function sources(detailFor: (id: string) => ExecutionDetail) {
    return {
      listExecutions: vi.fn(async () => [
        makeExecution({ id: 'execution-2', sequence: 2 }),
        makeExecution({ id: 'execution-1', sequence: 1, status: 'completed' }),
      ]),
      getExecution: vi.fn(async (id: string) => detailFor(id)),
    }
  }

  it('loads executions and the latest detail into progress state', async () => {
    const source = sources((id) =>
      makeExecutionDetail({
        id,
        status: 'running',
        steps: [
          makeStep({ id: 's1', sequence: 1, status: 'completed' }),
          makeStep({ id: 's2', sequence: 2, status: 'running' }),
        ],
      }),
    )
    const progress = useExecutionProgress(source, { taskId: () => 'task-1' })
    await progress.load()
    expect(progress.loading.value).toBe(false)
    expect(progress.executions.value.map((item) => item.id)).toEqual([
      'execution-2',
      'execution-1',
    ])
    expect(progress.detail.value?.id).toBe('execution-2')
    expect(progress.progress.value).toMatchObject({
      total: 2,
      completed: 1,
      percent: 50,
      currentStep: '解析可用文件',
    })
    progress.stopPolling()
  })

  it('clears detail when the task has no executions', async () => {
    const source = {
      listExecutions: vi.fn(async () => []),
      getExecution: vi.fn(async () => makeExecutionDetail()),
    }
    const progress = useExecutionProgress(source, { taskId: () => 'task-1' })
    await progress.load()
    expect(progress.detail.value).toBeNull()
    expect(source.getExecution).not.toHaveBeenCalled()
    progress.stopPolling()
  })

  it('polls while the execution is active and stops once it is terminal', async () => {
    vi.useFakeTimers()
    let status: ExecutionStatus = 'running'
    const source = {
      listExecutions: vi.fn(async () => [makeExecution({ id: 'execution-1' })]),
      getExecution: vi.fn(async () => makeExecutionDetail({ id: 'execution-1', status })),
    }
    const progress = useExecutionProgress(source, { taskId: () => 'task-1' })
    await progress.load()
    expect(source.getExecution).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(2000)
    expect(source.getExecution).toHaveBeenCalledTimes(2)

    status = 'completed'
    await vi.advanceTimersByTimeAsync(2000)
    expect(source.getExecution).toHaveBeenCalledTimes(3)
    await vi.advanceTimersByTimeAsync(6000)
    expect(source.getExecution).toHaveBeenCalledTimes(3)
    progress.stopPolling()
  })

  it('expands the failed run and refreshes history', async () => {
    vi.useFakeTimers()
    const source = {
      listExecutions: vi.fn(async () => [makeExecution({ id: 'execution-1' })]),
      getExecution: vi.fn(async () => makeExecutionDetail({ id: 'execution-1', status: 'running' })),
    }
    const progress = useExecutionProgress(source, { taskId: () => 'task-1' })
    await progress.load()
    source.getExecution.mockResolvedValueOnce(
      makeExecutionDetail({ id: 'execution-1', status: 'failed', error_message: '模型调用失败' }),
    )
    await vi.advanceTimersByTimeAsync(2000)
    expect(progress.expanded.value).toBe(true)
    await Promise.resolve()
    progress.stopPolling()
  })

  it('switches detail when selecting a history run', async () => {
    const source = sources((id) =>
      makeExecutionDetail({ id, status: id === 'execution-2' ? 'running' : 'completed' }),
    )
    const progress = useExecutionProgress(source, { taskId: () => 'task-1' })
    await progress.load()
    await progress.select(makeExecution({ id: 'execution-1', status: 'completed' }))
    expect(progress.detail.value?.id).toBe('execution-1')
    progress.stopPolling()
  })

  it('stops polling when a refresh fails', async () => {
    vi.useFakeTimers()
    const source = {
      listExecutions: vi.fn(async () => [makeExecution({ id: 'execution-1' })]),
      getExecution: vi.fn(async () => makeExecutionDetail({ id: 'execution-1', status: 'running' })),
    }
    const progress = useExecutionProgress(source, { taskId: () => 'task-1' })
    await progress.load()
    source.getExecution.mockRejectedValueOnce(new Error('network down'))
    await vi.advanceTimersByTimeAsync(2000)
    const calls = source.getExecution.mock.calls.length
    await vi.advanceTimersByTimeAsync(6000)
    expect(source.getExecution.mock.calls.length).toBe(calls)
    progress.stopPolling()
  })

  it('merges live events via applyEvent', async () => {
    const progress = useExecutionProgress(
      {
        listExecutions: async () => [],
        getExecution: async () => makeExecutionDetail(),
      },
      { taskId: () => 'task-1' },
    )
    progress.applyEvent('execution.started', { status: 'running' })
    progress.applyEvent('step.started', { step: eventStep({ status: 'running' }) })
    expect(progress.progressState.value.status).toBe('running')
    expect(progress.progress.value.running).toBe(1)
    progress.stopPolling()
  })
})
