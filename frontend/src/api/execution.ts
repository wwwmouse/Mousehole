import { ApiError } from './client'
import { createSseParser } from '@/utils/sse'

export type ExecutionEventName =
  | 'snapshot'
  | 'execution.started'
  | 'execution.completed'
  | 'execution.failed'
  | 'execution.cancelled'
  | 'step.started'
  | 'step.completed'
  | 'step.failed'
  | 'step.skipped'

export interface ExecutionEventHandlers {
  onEvent: (event: string, data: Record<string, unknown>) => void
  onError?: (error: ApiError) => void
}

const TERMINAL_EVENTS = new Set([
  'execution.completed',
  'execution.failed',
  'execution.cancelled',
])

/** True once the execution reached a final status event. */
export function isTerminalExecutionEvent(event: string): boolean {
  return TERMINAL_EVENTS.has(event)
}

/** Consume the execution SSE stream until it reaches a terminal status. */
export async function streamExecutionEvents(
  executionId: string,
  handlers: ExecutionEventHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(
    `/api/v1/executions/${encodeURIComponent(executionId)}/events`,
    { headers: { Accept: 'text/event-stream' }, signal },
  )
  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`
    try {
      const text = await response.text()
      const parsed = JSON.parse(text) as { error?: { message?: string } }
      message = parsed.error?.message ?? message
    } catch {
      /* keep default */
    }
    throw new ApiError(message, { code: 'http_error', status: response.status })
  }
  if (!response.body) {
    throw new ApiError('当前浏览器不支持流式响应', {
      code: 'stream_unsupported',
      status: 0,
    })
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = createSseParser({ skipComments: true })

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      for (const item of parser.feed(decoder.decode(value, { stream: true }))) {
        handlers.onEvent(item.event, item.data)
        if (isTerminalExecutionEvent(item.event)) return
      }
    }
  } finally {
    reader.cancel().catch(() => undefined)
  }
}
