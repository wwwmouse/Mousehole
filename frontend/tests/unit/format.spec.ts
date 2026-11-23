import { describe, expect, it } from 'vitest'

import {
  fileTypeLabel,
  formatBytes,
  formatDate,
  formatDateTime,
  formatRelative,
  greeting,
  parseDate,
  pluralize,
  projectStatusLabel,
  taskStatusLabel,
} from '@/utils/format'

describe('formatBytes', () => {
  it('renders bytes with the right unit and precision', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(10 * 1024)).toBe('10 KB')
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB')
  })

  it('handles missing / invalid input', () => {
    expect(formatBytes(null)).toBe('—')
    expect(formatBytes(undefined)).toBe('—')
    expect(formatBytes(Number.NaN)).toBe('—')
  })
})

describe('greeting', () => {
  it('maps the hour to the right greeting', () => {
    expect(greeting(new Date(2025, 0, 1, 4))).toBe('晚上好')
    expect(greeting(new Date(2025, 0, 1, 5))).toBe('早上好')
    expect(greeting(new Date(2025, 0, 1, 10))).toBe('早上好')
    expect(greeting(new Date(2025, 0, 1, 11))).toBe('中午好')
    expect(greeting(new Date(2025, 0, 1, 13))).toBe('下午好')
    expect(greeting(new Date(2025, 0, 1, 17))).toBe('下午好')
    expect(greeting(new Date(2025, 0, 1, 18))).toBe('晚上好')
    expect(greeting(new Date(2025, 0, 1, 0))).toBe('晚上好')
  })
})

describe('label helpers', () => {
  it('looks up known labels and falls back to the raw value', () => {
    expect(projectStatusLabel('active')).toBe('进行中')
    expect(projectStatusLabel('archived')).toBe('已归档')
    expect(projectStatusLabel('unknown')).toBe('unknown')
    expect(taskStatusLabel('completed')).toBe('已完成')
    expect(fileTypeLabel('md')).toBe('Markdown')
    expect(fileTypeLabel('pdf')).toBe('PDF')
    expect(fileTypeLabel('xyz')).toBe('XYZ')
    expect(pluralize(3)).toBe('3')
  })
})

describe('date helpers', () => {
  it('parses valid dates and rejects invalid input', () => {
    expect(parseDate('2025-01-02T03:04:05Z')).toBeInstanceOf(Date)
    expect(parseDate('not-a-date')).toBeNull()
    expect(parseDate(null)).toBeNull()
    expect(parseDate(undefined)).toBeNull()
  })

  it('renders an em dash for missing / invalid dates', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate('nope')).toBe('—')
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('nope')).toBe('—')
    expect(formatRelative(null)).toBe('—')
    expect(formatRelative('nope')).toBe('—')
  })
})
