import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import {
  dispatchChatEvent,
  normaliseChatEvent,
  type ChatPayload,
  type ChatStreamDone,
  type ChatToolResult,
} from '@/api/chat'
import {
  applyToolResult,
  createChatStreamState,
  finishChatStream,
  isAbortError,
  reduceChatStream,
  useChatStream,
  type ChatStreamState,
} from '@/composables/useChatStream'

function doneData(overrides: Partial<ChatStreamDone> = {}): ChatStreamDone {
  return {
    message_id: 'message-1',
    usage: null,
    task_usage: null,
    tools_enabled: false,
    artifacts: [],
    executions: [],
    ...overrides,
  }
}

function toolResult(overrides: Partial<ChatToolResult> = {}): ChatToolResult {
  return {
    name: 'read_task_files',
    ok: true,
    summary: '2 个文件',
    artifact_id: null,
    execution_id: null,
    ...overrides,
  }
}

function applyAll(events: Parameters<typeof reduceChatStream>[1][]): ChatStreamState {
  return events.reduce(
    (state, event) => reduceChatStream(state, event),
    createChatStreamState(),
  )
}

afterEach(() => {
  vi.useRealTimers()
})

describe('normaliseChatEvent', () => {
  it('normalises a start event with provider/model defaults', () => {
    expect(normaliseChatEvent('start', { provider: 'deepseek' })).toEqual({
      type: 'start',
      data: { provider: 'deepseek', model: '' },
    })
  })

  it('normalises delta text and falls back to an empty string', () => {
    expect(normaliseChatEvent('delta', { text: '你好' })).toEqual({
      type: 'delta',
      text: '你好',
    })
    expect(normaliseChatEvent('delta', {})).toEqual({ type: 'delta', text: '' })
  })

  it('normalises thinking / tool_call / tool_result / done / error', () => {
    expect(normaliseChatEvent('thinking', {})).toEqual({ type: 'thinking' })

    expect(
      normaliseChatEvent('tool_call', { name: 'save_artifact', arguments: { title: 'x' } }),
    ).toEqual({
      type: 'tool_call',
      call: { name: 'save_artifact', arguments: { title: 'x' } },
    })
    expect(normaliseChatEvent('tool_call', { name: 'save_artifact' })).toEqual({
      type: 'tool_call',
      call: { name: 'save_artifact', arguments: {} },
    })

    expect(
      normaliseChatEvent('tool_result', {
        name: 'read_task_files',
        ok: false,
        summary: '失败',
        artifact_id: 'artifact-1',
        execution_id: null,
      }),
    ).toEqual({
      type: 'tool_result',
      result: {
        name: 'read_task_files',
        ok: false,
        summary: '失败',
        artifact_id: 'artifact-1',
        execution_id: null,
      },
    })

    expect(normaliseChatEvent('done', { message_id: 'm1', artifacts: ['a1'] })).toEqual({
      type: 'done',
      data: {
        message_id: 'm1',
        usage: null,
        task_usage: null,
        tools_enabled: false,
        artifacts: ['a1'],
        executions: [],
        citations: [],
      },
    })

    expect(normaliseChatEvent('error', {})).toEqual({
      type: 'error',
      error: { code: 'provider_error', message: '模型调用失败' },
    })
    expect(normaliseChatEvent('error', { code: 'rate_limited', message: '太快了' })).toEqual({
      type: 'error',
      error: { code: 'rate_limited', message: '太快了' },
    })
  })

  it('returns null for unknown / keepalive events', () => {
    expect(normaliseChatEvent('message', { text: 'x' })).toBeNull()
    expect(normaliseChatEvent('keepalive', {})).toBeNull()
  })

  it('dispatches typed events to the legacy callbacks', () => {
    const deltas: string[] = []
    const dones: ChatStreamDone[] = []
    dispatchChatEvent(
      { type: 'delta', text: 'a' },
      { onDelta: (text) => deltas.push(text) },
    )
    dispatchChatEvent(
      { type: 'done', data: doneData({ message_id: 'm9' }) },
      { onDone: (data) => dones.push(data) },
    )
    expect(deltas).toEqual(['a'])
    expect(dones[0].message_id).toBe('m9')
  })
})

describe('reduceChatStream', () => {
  it('accumulates deltas and clears the thinking flag', () => {
    const state = applyAll([
      { type: 'thinking' },
      { type: 'delta', text: '你' },
      { type: 'delta', text: '好' },
    ])
    expect(state.streamText).toBe('你好')
    expect(state.thinking).toBe(false)
  })

  it('records start and thinking events', () => {
    const state = applyAll([
      { type: 'start', data: { provider: 'ollama', model: 'qwen' } },
      { type: 'thinking' },
    ])
    expect(state.started).toEqual({ provider: 'ollama', model: 'qwen' })
    expect(state.thinking).toBe(true)
  })

  it('appends tool calls and completes the matching running call', () => {
    const state = applyAll([
      { type: 'tool_call', call: { name: 'read_task_files', arguments: {} } },
      { type: 'tool_call', call: { name: 'save_artifact', arguments: {} } },
      { type: 'tool_result', result: toolResult({ ok: false, summary: '读取失败' }) },
    ])
    expect(state.toolEvents).toEqual([
      { name: 'read_task_files', status: 'error', summary: '读取失败' },
      { name: 'save_artifact', status: 'running', summary: '' },
    ])
  })

  it('marks tool calls as ok on success', () => {
    const state = applyAll([
      { type: 'tool_call', call: { name: 'read_task_files', arguments: {} } },
      { type: 'tool_result', result: toolResult() },
    ])
    expect(state.toolEvents[0]).toMatchObject({ status: 'ok', summary: '2 个文件' })
  })

  it('leaves events untouched when no running call matches the result', () => {
    const events = [{ name: 'read_task_files', status: 'ok' as const, summary: '' }]
    expect(applyToolResult(events, toolResult())).toEqual(events)
  })

  it('records a mid-stream error without losing partial text', () => {
    const state = applyAll([
      { type: 'delta', text: '部分内容' },
      { type: 'error', error: { code: 'provider_error', message: '模型调用失败' } },
    ])
    expect(state.streamText).toBe('部分内容')
    expect(state.error).toBe('模型调用失败')
    expect(state.failed).toBe(true)
    expect(state.thinking).toBe(false)
  })

  it('merges a done event into usage / artifacts / executions', () => {
    const state = applyAll([
      {
        type: 'done',
        data: doneData({
          message_id: 'm42',
          usage: { total_tokens: 10 },
          task_usage: { total_tokens: 100 },
          artifacts: ['a1', 'a2'],
          executions: ['e1'],
          tools_enabled: true,
        }),
      },
    ])
    expect(state.done).toBe(true)
    expect(state.messageId).toBe('m42')
    expect(state.messageUsage).toEqual({ total_tokens: 10 })
    expect(state.taskUsage).toEqual({ total_tokens: 100 })
    expect(state.artifacts).toEqual(['a1', 'a2'])
    expect(state.executions).toEqual(['e1'])
    expect(state.thinking).toBe(false)
  })

  it('finishChatStream only clears the thinking flag', () => {
    const state = reduceChatStream(createChatStreamState(), { type: 'thinking' })
    expect(state.thinking).toBe(true)
    expect(finishChatStream(state).thinking).toBe(false)
    expect(finishChatStream(state).done).toBe(false)
  })
})

describe('isAbortError', () => {
  it('recognises AbortError only', () => {
    expect(isAbortError(new DOMException('aborted', 'AbortError'))).toBe(true)
    expect(isAbortError(new Error('boom'))).toBe(false)
    expect(isAbortError(null)).toBe(false)
    expect(isAbortError('AbortError')).toBe(false)
  })
})

describe('useChatStream', () => {
  it('resets state and counts elapsed seconds while sending', () => {
    vi.useFakeTimers()
    const chat = useChatStream()
    chat.setError('previous error')
    chat.begin()
    expect(chat.sending.value).toBe(true)
    expect(chat.error.value).toBeNull()
    expect(chat.elapsed.value).toBe(0)
    vi.advanceTimersByTime(2500)
    expect(chat.elapsed.value).toBe(2)
    chat.dispose()
  })

  it('streams a fake turn: deltas, tool call/result, done callback', async () => {
    const seen: ChatStreamDone[] = []
    const chat = useChatStream({
      onDone: (data) => seen.push(data),
      runner: async (_taskId, _payload, handlers) => {
        handlers.onEvent?.({ type: 'thinking' })
        handlers.onEvent?.({ type: 'delta', text: '你' })
        handlers.onEvent?.({ type: 'delta', text: '好' })
        handlers.onEvent?.({ type: 'tool_call', call: { name: 'read_task_files', arguments: {} } })
        handlers.onEvent?.({
          type: 'tool_result',
          result: toolResult(),
        })
        handlers.onEvent?.({
          type: 'done',
          data: doneData({ message_id: 'm1', task_usage: { total_tokens: 12 } }),
        })
      },
    })
    chat.begin()
    const outcome = await chat.run('task-1', { content: '你好' })
    expect(outcome).toBe('done')
    expect(chat.sending.value).toBe(false)
    expect(chat.streamText.value).toBe('你好')
    expect(chat.thinking.value).toBe(false)
    expect(chat.toolEvents.value).toEqual([
      { name: 'read_task_files', status: 'ok', summary: '2 个文件' },
    ])
    expect(chat.taskUsage.value).toEqual({ total_tokens: 12 })
    expect(chat.done.value).toBe(true)
    expect(seen).toHaveLength(1)
    chat.dispose()
  })

  it('turns an HTTP/ApiError failure into error state + outcome', async () => {
    const chat = useChatStream({
      runner: async () => {
        throw new ApiError('尚未配置模型', { code: 'model_required', status: 422 })
      },
    })
    chat.begin()
    const outcome = await chat.run('task-1', { content: 'x' })
    expect(outcome).toBe('error')
    expect(chat.error.value).toBe('尚未配置模型')
    expect(chat.failed.value).toBe(true)
    expect(chat.sending.value).toBe(false)
    chat.dispose()
  })

  it('reports an outcome of error when a mid-stream error event arrives', async () => {
    const chat = useChatStream({
      runner: async (_taskId, _payload, handlers) => {
        handlers.onEvent?.({
          type: 'error',
          error: { code: 'provider_error', message: '上游失败' },
        })
      },
    })
    chat.begin()
    await expect(chat.run('task-1', { content: 'x' })).resolves.toBe('error')
    expect(chat.error.value).toBe('上游失败')
    chat.dispose()
  })

  it('reports aborted when the user stops the stream', async () => {
    const chat = useChatStream({
      runner: (_taskId, _payload, _handlers, signal) =>
        new Promise<void>((_resolve, reject) => {
          signal?.addEventListener('abort', () => {
            reject(new DOMException('The operation was aborted.', 'AbortError'))
          })
        }),
    })
    chat.begin()
    const pending = chat.run('task-1', { content: 'long' })
    chat.stop()
    await expect(pending).resolves.toBe('aborted')
    expect(chat.error.value).toBeNull()
    expect(chat.sending.value).toBe(false)
    chat.dispose()
  })

  it('forwards the chat/work mode in the payload', async () => {
    const payloads: ChatPayload[] = []
    const chat = useChatStream({
      runner: async (_taskId, payload) => {
        payloads.push(payload)
      },
    })
    chat.begin()
    await chat.run('task-1', { content: '普通问题', mode: 'chat' })
    await chat.run('task-1', { content: '分析文件', mode: 'work' })
    expect(payloads).toEqual([
      { content: '普通问题', mode: 'chat' },
      { content: '分析文件', mode: 'work' },
    ])
    chat.dispose()
  })

  it('setError shows a message without starting a stream', () => {
    const chat = useChatStream()
    chat.setError('尚未配置可用模型')
    expect(chat.error.value).toBe('尚未配置可用模型')
    expect(chat.sending.value).toBe(false)
  })
})
