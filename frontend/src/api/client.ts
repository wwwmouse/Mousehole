/**
 * HTTP client: one place for base URL, timeouts, JSON handling and error
 * normalisation into ApiError. All views talk through this module only.
 */

const API_BASE = '/api/v1'
const DEFAULT_TIMEOUT_MS = 30_000

export interface ApiErrorInit {
  code: string
  status: number
  details?: unknown
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: unknown

  constructor(message: string, init: ApiErrorInit) {
    super(message)
    this.name = 'ApiError'
    this.code = init.code
    this.status = init.status
    this.details = init.details ?? null
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError
}

export type QueryValue = string | number | boolean | null | undefined

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  query?: Record<string, QueryValue>
  json?: unknown
  form?: FormData
  timeoutMs?: number
  signal?: AbortSignal
}

interface ErrorEnvelopeShape {
  error?: {
    code?: unknown
    message?: unknown
    details?: unknown
  }
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const search = new URLSearchParams()
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === null || value === undefined || value === '') continue
      search.set(key, String(value))
    }
  }
  const suffix = search.toString()
  return `${API_BASE}${path}${suffix ? `?${suffix}` : ''}`
}

function normaliseError(
  status: number,
  payload: unknown,
): { code: string; message: string; details: unknown } {
  if (payload && typeof payload === 'object') {
    const envelope = payload as ErrorEnvelopeShape
    const error = envelope.error
    if (error && typeof error === 'object') {
      const code = typeof error.code === 'string' && error.code ? error.code : 'http_error'
      const message =
        typeof error.message === 'string' && error.message
          ? error.message
          : `请求失败（HTTP ${status}）`
      return { code, message, details: error.details ?? null }
    }
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail) {
      return { code: status === 404 ? 'not_found' : 'http_error', message: detail, details: null }
    }
  }
  switch (status) {
    case 401:
      return { code: 'unauthorized', message: '未授权，请检查服务配置', details: null }
    case 404:
      return { code: 'not_found', message: '请求的资源不存在', details: null }
    case 409:
      return { code: 'conflict', message: '资源存在冲突，操作未完成', details: null }
    case 415:
      return { code: 'unsupported_file_type', message: '不支持的文件类型', details: null }
    case 422:
      return { code: 'validation_error', message: '请求参数不合法', details: null }
    default:
      return { code: 'http_error', message: `请求失败（HTTP ${status}）`, details: null }
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    method = 'GET',
    query,
    json,
    form,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal,
  } = options

  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  const onExternalAbort = () => controller.abort()
  if (signal) {
    if (signal.aborted) controller.abort()
    else signal.addEventListener('abort', onExternalAbort, { once: true })
  }

  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  } else if (form) {
    body = form
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body,
      signal: controller.signal,
    })
  } catch {
    if (timedOut) {
      throw new ApiError('请求超时，请稍后重试', { code: 'timeout', status: 0 })
    }
    if (signal?.aborted) {
      throw new ApiError('请求已取消', { code: 'aborted', status: 0 })
    }
    throw new ApiError('无法连接到服务器，请确认后端服务已启动', {
      code: 'network_error',
      status: 0,
    })
  } finally {
    clearTimeout(timer)
    if (signal) signal.removeEventListener('abort', onExternalAbort)
  }

  const text = await response.text().catch(() => '')
  let payload: unknown
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!response.ok) {
    const info = normaliseError(response.status, payload)
    throw new ApiError(info.message, {
      code: info.code,
      status: response.status,
      details: info.details,
    })
  }

  if (response.status === 204 || !text) return undefined as T
  return payload as T
}
