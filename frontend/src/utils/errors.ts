import { ApiError, isApiError } from '@/api/client'

export interface ReferenceInfo {
  kind: string
  id: string
  name: string
}

/** Human-readable message for any thrown value. Never fabricates success. */
export function errorMessage(error: unknown): string {
  if (isApiError(error)) return error.message
  if (error instanceof Error && error.message) return error.message
  return '操作失败，请稍后重试'
}

/** Optional secondary detail line (e.g. backend error code). */
export function errorDetail(error: unknown): string | null {
  if (isApiError(error) && error.code) {
    return error.code === 'network_error' ? 'network_error' : `${error.code} · HTTP ${error.status || '—'}`
  }
  return null
}

export function isNotFound(error: unknown): boolean {
  return isApiError(error) && error.status === 404
}

function isReference(value: unknown): value is ReferenceInfo {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return typeof record.kind === 'string' && typeof record.name === 'string'
}

/**
 * Extract file reference list from a 409 conflict response.
 * Supported shapes:
 *   - bare array of { kind, id, name }
 *   - { references: [...] }
 *   - { projects: [{ id, name }], tasks: [{ id, title }] }  (files API)
 */
export function extractReferences(error: unknown): ReferenceInfo[] {
  if (!isApiError(error) || !error.details) return []
  const details = error.details
  if (Array.isArray(details)) return details.filter(isReference)
  if (!details || typeof details !== 'object') return []
  const record = details as Record<string, unknown>
  const references = record.references
  if (Array.isArray(references)) return references.filter(isReference)

  const collected: ReferenceInfo[] = []
  if (Array.isArray(record.projects)) {
    for (const item of record.projects) {
      if (!item || typeof item !== 'object') continue
      const project = item as Record<string, unknown>
      if (typeof project.id === 'string' && typeof project.name === 'string') {
        collected.push({ kind: 'project', id: project.id, name: project.name })
      }
    }
  }
  if (Array.isArray(record.tasks)) {
    for (const item of record.tasks) {
      if (!item || typeof item !== 'object') continue
      const task = item as Record<string, unknown>
      if (typeof task.id === 'string') {
        const name = typeof task.title === 'string' ? task.title : typeof task.name === 'string' ? task.name : task.id
        collected.push({ kind: 'task', id: task.id, name })
      }
    }
  }
  return collected
}

export function isConflict(error: unknown): boolean {
  return isApiError(error) && error.status === 409
}

export function isUnsupportedFileType(error: unknown): boolean {
  return isApiError(error) && (error.status === 415 || error.code === 'unsupported_file_type')
}

export { ApiError }
