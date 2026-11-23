import { describe, expect, it } from 'vitest'

import {
  chainDuration,
  fileSourceLabel,
  fileStatusHint,
  FILE_SOURCE_LABELS,
  formatDurationMs,
  formatElapsedSeconds,
  messageFiles,
  messageTools,
  toolLabel,
  TOOL_LABELS,
  usageLabel,
} from '@/utils/chat'
import { makeMessage } from './factories'

describe('tool / file source labels', () => {
  it('maps known tool names and falls back to the raw name', () => {
    expect(toolLabel('read_task_files')).toBe(TOOL_LABELS.read_task_files)
    expect(toolLabel('create_execution')).toBe('启动执行')
    expect(toolLabel('custom_tool')).toBe('custom_tool')
  })

  it('maps file sources and falls back to the raw source', () => {
    expect(fileSourceLabel('project_inherited')).toBe(FILE_SOURCE_LABELS.project_inherited)
    expect(fileSourceLabel('task_added')).toBe('额外引用')
    expect(fileSourceLabel('temporary')).toBe('本轮临时')
    expect(fileSourceLabel('skill_asset')).toBe('Skill 资料')
    expect(fileSourceLabel('other')).toBe('other')
  })

  it('explains non-included file statuses only', () => {
    expect(fileStatusHint('skipped')).toBe('（超预算未展开）')
    expect(fileStatusHint('failed')).toBe('（读取失败）')
    expect(fileStatusHint('included')).toBe('')
    expect(fileStatusHint(undefined)).toBe('')
  })
})

describe('duration / usage formatting', () => {
  it('formats millisecond durations for the thought chain', () => {
    expect(formatDurationMs(1500)).toBe('1.5s')
    expect(formatDurationMs(250)).toBe('0.3s')
    expect(formatDurationMs(0)).toBe('')
    expect(formatDurationMs(-10)).toBe('')
    expect(formatDurationMs(null)).toBe('')
    expect(formatDurationMs(undefined)).toBe('')
  })

  it('formats elapsed seconds for the streaming bubble', () => {
    expect(formatElapsedSeconds(0)).toBe('0s')
    expect(formatElapsedSeconds(12)).toBe('12s')
    expect(formatElapsedSeconds(12.9)).toBe('12s')
    expect(formatElapsedSeconds(-3)).toBe('0s')
  })

  it('formats the per-message token usage label', () => {
    expect(usageLabel(null)).toBeNull()
    expect(usageLabel(undefined)).toBeNull()
    expect(usageLabel({})).toBeNull()
    expect(usageLabel({ total_tokens: 0 })).toBeNull()
    expect(usageLabel({ total_tokens: 42 })).toBe('42 tokens')
  })
})

describe('message metadata helpers', () => {
  it('reads the tool chain duration from metadata', () => {
    expect(chainDuration(makeMessage({ metadata: { duration_ms: 1500 } }))).toBe('1.5s')
    expect(chainDuration(makeMessage({ metadata: {} }))).toBe('')
    expect(chainDuration(makeMessage({ metadata: null }))).toBe('')
  })

  it('defaults tools / files metadata to empty arrays', () => {
    expect(messageTools(makeMessage())).toEqual([])
    expect(messageFiles(makeMessage())).toEqual([])
    const withMeta = makeMessage({
      metadata: {
        tools: [{ name: 'read_task_files', ok: true, summary: 'ok' }],
        files: [{ filename: 'a.md', source: 'temporary', status: 'included' }],
      },
    })
    expect(messageTools(withMeta)).toHaveLength(1)
    expect(messageFiles(withMeta)).toHaveLength(1)
  })
})
