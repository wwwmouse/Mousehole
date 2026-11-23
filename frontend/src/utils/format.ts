const dateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'long',
})

const relativeFormatter = new Intl.RelativeTimeFormat('zh-CN', { numeric: 'auto' })

export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDateTime(value: string | null | undefined): string {
  const date = parseDate(value)
  return date ? dateTimeFormatter.format(date) : '—'
}

export function formatDate(value: string | Date | null | undefined): string {
  const date = value instanceof Date ? value : parseDate(value)
  return date ? dateFormatter.format(date) : '—'
}

export function formatRelative(value: string | null | undefined): string {
  const date = parseDate(value)
  if (!date) return '—'
  const diffSeconds = (date.getTime() - Date.now()) / 1000
  const absolute = Math.abs(diffSeconds)
  if (absolute < 60) return '刚刚'
  if (absolute < 3600) return relativeFormatter.format(Math.round(diffSeconds / 60), 'minute')
  if (absolute < 86_400) return relativeFormatter.format(Math.round(diffSeconds / 3600), 'hour')
  if (absolute < 86_400 * 30) return relativeFormatter.format(Math.round(diffSeconds / 86_400), 'day')
  return formatDate(date)
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`
}

export function greeting(now: Date = new Date()): string {
  const hour = now.getHours()
  if (hour >= 5 && hour < 11) return '早上好'
  if (hour >= 11 && hour < 13) return '中午好'
  if (hour >= 13 && hour < 18) return '下午好'
  return '晚上好'
}

const projectStatusLabels: Record<string, string> = {
  active: '进行中',
  archived: '已归档',
}

const taskStatusLabels: Record<string, string> = {
  active: '进行中',
  completed: '已完成',
  archived: '已归档',
}

const fileTypeLabels: Record<string, string> = {
  pdf: 'PDF',
  md: 'Markdown',
  markdown: 'Markdown',
  text: 'TXT',
  txt: 'TXT',
  json: 'JSON',
  yaml: 'YAML',
  yml: 'YAML',
  csv: 'CSV',
  html: 'HTML',
  css: 'CSS',
}

export function projectStatusLabel(status: string): string {
  return projectStatusLabels[status] ?? status
}

export function taskStatusLabel(status: string): string {
  return taskStatusLabels[status] ?? status
}

export function fileTypeLabel(type: string): string {
  return fileTypeLabels[type] ?? type.toUpperCase()
}

export function pluralize(count: number): string {
  return String(count)
}
