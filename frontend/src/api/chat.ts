import { ApiError } from './client'
import { createSseParser } from '@/utils/sse'

export interface ChatStreamStart {
  provider: string
  model: string
}

export interface ChatStreamDone {
  message_id: string
  usage: Record<string, number> | null
  task_usage: Record<string, number> | null
  tools_enabled: boolean
  artifacts: string[]
  executions: string[]
  citations?: Array<{
    file_id: string
    filename: string
    page_no: number
  }>
}

export interface ChatToolCall {
  name: string
  arguments: Record<string, unknown>
}

export interface ChatToolResult {
  name: string
  ok: boolean
  summary: string
  artifact_id: string | null
  execution_id: string | null
}

/**
 * Normalised chat stream event. Parsing (SSE framing + JSON + field
 * normalisation) lives in `normaliseChatEvent`, so the same logic is reused by
 * the raw fetch client below and by `useChatStream` (and unit tests) without
 * duplicating the protocol.
 */
export type ChatStreamEvent =
  | { type: 'start'; data: ChatStreamStart }
  | { type: 'delta'; text: string }
  | { type: 'thinking' }
  | { type: 'tool_call'; call: ChatToolCall }
  | { type: 'tool_result'; result: ChatToolResult }
  | { type: 'done'; data: ChatStreamDone }
  | { type: 'error'; error: { code: string; message: string } }

export interface ChatStreamHandlers {
  /** Receives every known event. Prefer this over the per-kind callbacks. */
  onEvent?: (event: ChatStreamEvent) => void
  onStart?: (data: ChatStreamStart) => void
  onDelta?: (text: string) => void
  onDone?: (data: ChatStreamDone) => void
  onError?: (error: { code: string; message: string }) => void
  onToolCall?: (data: ChatToolCall) => void
  onToolResult?: (data: ChatToolResult) => void
  onThinking?: () => void
}

export type ChatMode = 'chat' | 'work'

export interface ChatPayload {
  content: string
  provider?: string
  model?: string
  skill_id?: string
  file_ids?: string[]
  /**
   * Phase 5 H4: chat = no tool calls; work = tools are offered and the model
   * decides whether to use them. Backend defaults to work.
   */
  mode?: ChatMode
}

function asString(value: unknown, fallback = ''): string {
  return value === null || value === undefined ? fallback : String(value)
}

function asNumberRecord(value: unknown): Record<string, number> | null {
  if (!value || typeof value !== 'object') return null
  return value as Record<string, number>
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : []
}

/**
 * Map a decoded SSE event name + JSON payload to a typed chat stream event.
 * Unknown event names return null (the UI simply ignores them).
 */
export function normaliseChatEvent(
  event: string,
  data: Record<string, unknown>,
): ChatStreamEvent | null {
  if (event === 'start') {
    return {
      type: 'start',
      data: { provider: asString(data.provider), model: asString(data.model) },
    }
  }
  if (event === 'delta') return { type: 'delta', text: asString(data.text) }
  if (event === 'thinking') return { type: 'thinking' }
  if (event === 'tool_call') {
    return {
      type: 'tool_call',
      call: {
        name: asString(data.name),
        arguments: (data.arguments as Record<string, unknown> | undefined) ?? {},
      },
    }
  }
  if (event === 'tool_result') {
    return {
      type: 'tool_result',
      result: {
        name: asString(data.name),
        ok: Boolean(data.ok),
        summary: asString(data.summary),
        artifact_id: (data.artifact_id as string | null) ?? null,
        execution_id: (data.execution_id as string | null) ?? null,
      },
    }
  }
  if (event === 'done') {
    return {
      type: 'done',
      data: {
        message_id: asString(data.message_id),
        usage: asNumberRecord(data.usage),
        task_usage: asNumberRecord(data.task_usage),
        tools_enabled: Boolean(data.tools_enabled),
        artifacts: asStringArray(data.artifacts),
        executions: asStringArray(data.executions),
        citations: Array.isArray(data.citations)
          ? data.citations
              .filter(
                (item): item is Record<string, unknown> =>
                  Boolean(item) && typeof item === 'object',
              )
              .map((item) => ({
                file_id: asString(item.file_id),
                filename: asString(item.filename),
                page_no: Number(item.page_no) || 0,
              }))
              .filter((item) => item.file_id && item.page_no > 0)
          : [],
      },
    }
  }
  if (event === 'error') {
    return {
      type: 'error',
      error: {
        code: asString(data.code, 'provider_error'),
        message: asString(data.message, '模型调用失败'),
      },
    }
  }
  return null
}

/** Dispatch a typed event to the matching legacy callback (if any). */
export function dispatchChatEvent(
  event: ChatStreamEvent,
  handlers: ChatStreamHandlers,
): void {
  handlers.onEvent?.(event)
  switch (event.type) {
    case 'start':
      handlers.onStart?.(event.data)
      break
    case 'delta':
      handlers.onDelta?.(event.text)
      break
    case 'thinking':
      handlers.onThinking?.()
      break
    case 'tool_call':
      handlers.onToolCall?.(event.call)
      break
    case 'tool_result':
      handlers.onToolResult?.(event.result)
      break
    case 'done':
      handlers.onDone?.(event.data)
      break
    case 'error':
      handlers.onError?.(event.error)
      break
  }
}

/**
 * POST a chat message and consume the SSE stream.
 * Throws ApiError for HTTP-level failures (e.g. 422 model_required); model
 * errors that happen mid-stream arrive through handlers.onError instead.
 */
export async function streamTaskChat(
  taskId: string,
  payload: ChatPayload,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/messages`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(payload),
      signal,
    },
  )

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    let code = 'http_error'
    let message = `请求失败（HTTP ${response.status}）`
    try {
      const parsed = JSON.parse(text) as { error?: { code?: string; message?: string } }
      if (parsed.error) {
        code = parsed.error.code ?? code
        message = parsed.error.message ?? message
      }
    } catch {
      /* keep defaults */
    }
    throw new ApiError(message, { code, status: response.status })
  }

  if (!response.body) {
    throw new ApiError('当前浏览器不支持流式响应', {
      code: 'stream_unsupported',
      status: 0,
    })
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = createSseParser()

  function emit(event: string, data: Record<string, unknown>): void {
    const normalised = normaliseChatEvent(event, data)
    if (normalised) dispatchChatEvent(normalised, handlers)
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    for (const item of parser.feed(decoder.decode(value, { stream: true }))) {
      emit(item.event, item.data)
    }
  }
  for (const item of parser.flush()) emit(item.event, item.data)
}
