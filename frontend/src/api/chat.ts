import { ApiError } from './client'

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

export interface ChatStreamHandlers {
  onStart?: (data: ChatStreamStart) => void
  onDelta: (text: string) => void
  onDone: (data: ChatStreamDone) => void
  onError: (error: { code: string; message: string }) => void
  onToolCall?: (data: ChatToolCall) => void
  onToolResult?: (data: ChatToolResult) => void
  onThinking?: () => void
}

interface ChatPayload {
  content: string
  provider?: string
  model?: string
}

function parseEvent(raw: string, handlers: ChatStreamHandlers): void {
  const lines = raw.split('\n')
  let event = 'message'
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (dataLines.length === 0) return
  let data: Record<string, unknown>
  try {
    data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
  } catch {
    return
  }
  if (event === 'start') {
    handlers.onStart?.({
      provider: String(data.provider ?? ''),
      model: String(data.model ?? ''),
    })
  } else if (event === 'delta') {
    handlers.onDelta(String(data.text ?? ''))
  } else if (event === 'thinking') {
    handlers.onThinking?.()
  } else if (event === 'tool_call') {
    handlers.onToolCall?.({
      name: String(data.name ?? ''),
      arguments:
        (data.arguments as Record<string, unknown> | undefined) ?? {},
    })
  } else if (event === 'tool_result') {
    handlers.onToolResult?.({
      name: String(data.name ?? ''),
      ok: Boolean(data.ok),
      summary: String(data.summary ?? ''),
      artifact_id: (data.artifact_id as string | null) ?? null,
      execution_id: (data.execution_id as string | null) ?? null,
    })
  } else if (event === 'done') {
    handlers.onDone({
      message_id: String(data.message_id ?? ''),
      usage: (data.usage as Record<string, number> | null) ?? null,
      task_usage: (data.task_usage as Record<string, number> | null) ?? null,
      tools_enabled: Boolean(data.tools_enabled),
      artifacts: (data.artifacts as string[] | undefined) ?? [],
      executions: (data.executions as string[] | undefined) ?? [],
    })
  } else if (event === 'error') {
    handlers.onError({
      code: String(data.code ?? 'provider_error'),
      message: String(data.message ?? '模型调用失败'),
    })
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
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let index = buffer.indexOf('\n\n')
    while (index >= 0) {
      const chunk = buffer.slice(0, index)
      buffer = buffer.slice(index + 2)
      if (chunk.trim()) parseEvent(chunk, handlers)
      index = buffer.indexOf('\n\n')
    }
  }
  if (buffer.trim()) parseEvent(buffer, handlers)
}
