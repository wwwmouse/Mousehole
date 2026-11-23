import { describe, expect, it } from 'vitest'

import { ApiError } from '@/api/client'
import {
  errorDetail,
  errorMessage,
  extractReferences,
  isConflict,
  isNotFound,
  isUnsupportedFileType,
} from '@/utils/errors'

describe('errorMessage', () => {
  it('uses the ApiError message', () => {
    expect(errorMessage(new ApiError('任务不存在', { code: 'not_found', status: 404 }))).toBe(
      '任务不存在',
    )
  })

  it('falls back to Error.message', () => {
    expect(errorMessage(new Error('boom'))).toBe('boom')
  })

  it('never fabricates success for unknown values', () => {
    expect(errorMessage(new Error(''))).toBe('操作失败，请稍后重试')
    expect(errorMessage('string error')).toBe('操作失败，请稍后重试')
    expect(errorMessage(42)).toBe('操作失败，请稍后重试')
    expect(errorMessage(null)).toBe('操作失败，请稍后重试')
  })
})

describe('errorDetail', () => {
  it('shows code + HTTP status for ApiError', () => {
    expect(
      errorDetail(new ApiError('冲突', { code: 'conflict', status: 409 })),
    ).toBe('conflict · HTTP 409')
  })

  it('collapses network errors to a single token', () => {
    expect(
      errorDetail(new ApiError('无法连接', { code: 'network_error', status: 0 })),
    ).toBe('network_error')
  })

  it('returns null for non-API errors', () => {
    expect(errorDetail(new Error('boom'))).toBeNull()
    expect(errorDetail(null)).toBeNull()
  })
})

describe('status predicates', () => {
  it('recognises 404 / 409 / unsupported file type', () => {
    expect(isNotFound(new ApiError('x', { code: 'not_found', status: 404 }))).toBe(true)
    expect(isNotFound(new ApiError('x', { code: 'conflict', status: 409 }))).toBe(false)
    expect(isConflict(new ApiError('x', { code: 'conflict', status: 409 }))).toBe(true)
    expect(isUnsupportedFileType(new ApiError('x', { code: 'weird', status: 415 }))).toBe(true)
    expect(
      isUnsupportedFileType(new ApiError('x', { code: 'unsupported_file_type', status: 400 })),
    ).toBe(true)
    expect(isUnsupportedFileType(new Error('x'))).toBe(false)
  })
})

describe('extractReferences', () => {
  it('reads a bare reference array', () => {
    const error = new ApiError('conflict', {
      code: 'conflict',
      status: 409,
      details: [
        { kind: 'task', id: 't1', name: '任务 A' },
        { kind: 'project', id: 'p1' },
      ],
    })
    expect(extractReferences(error)).toEqual([{ kind: 'task', id: 't1', name: '任务 A' }])
  })

  it('reads the { references } shape', () => {
    const error = new ApiError('conflict', {
      code: 'conflict',
      status: 409,
      details: { references: [{ kind: 'file', id: 'f1', name: 'a.md' }] },
    })
    expect(extractReferences(error)).toEqual([{ kind: 'file', id: 'f1', name: 'a.md' }])
  })

  it('reads the files API { projects, tasks } shape', () => {
    const error = new ApiError('conflict', {
      code: 'conflict',
      status: 409,
      details: {
        projects: [{ id: 'p1', name: 'Project A' }],
        tasks: [{ id: 't1', title: 'Task A' }, { id: 't2' }],
      },
    })
    expect(extractReferences(error)).toEqual([
      { kind: 'project', id: 'p1', name: 'Project A' },
      { kind: 'task', id: 't1', name: 'Task A' },
      { kind: 'task', id: 't2', name: 't2' },
    ])
  })

  it('returns [] for non-conflict / malformed payloads', () => {
    expect(extractReferences(new Error('boom'))).toEqual([])
    expect(
      extractReferences(new ApiError('x', { code: 'conflict', status: 409, details: null })),
    ).toEqual([])
    expect(
      extractReferences(new ApiError('x', { code: 'conflict', status: 409, details: 'oops' })),
    ).toEqual([])
  })
})
