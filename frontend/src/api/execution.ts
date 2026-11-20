import { ApiError } from './client'

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

const TERMINAL = new Set([
  'execution.completed',
  'execution.failed',
  'execution.cancelled',
])

function parseChunk(raw: string): { event: string; data: Record<string, unknown> } | null {
  const lines = raw.split('\n')
  let event = 'message'
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (dataLines.length === 0) return null
  try {
    return { event, data: JSON.parse(dataLines.join('\n')) as Record<string, unknown> }
  } catch {
    return null
  }
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
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let index = buffer.indexOf('\n\n')
      while (index >= 0) {
        const chunk = buffer.slice(0, index)
        buffer = buffer.slice(index + 2)
        if (chunk.trim() && !chunk.startsWith(':')) {
          const parsed = parseChunk(chunk)
          if (parsed) {
            handlers.onEvent(parsed.event, parsed.data)
            if (TERMINAL.has(parsed.event)) return
          }
        }
        index = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.cancel().catch(() => undefined)
  }
}
