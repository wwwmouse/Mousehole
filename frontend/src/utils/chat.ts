import type {
  ChatMessage,
  MessageFileMeta,
  MessageToolMeta,
  TaskUsage,
} from '@/api/types'

/** Tool names shown in the thought chain / work log. */
export const TOOL_LABELS: Record<string, string> = {
  read_task_files: '读取可用文件',
  read_task_file: '读取文件内容',
  save_artifact: '保存成果',
  create_execution: '启动执行',
}

/** Where an attached file came from (message metadata / task context). */
export const FILE_SOURCE_LABELS: Record<string, string> = {
  project_inherited: '项目继承',
  task_added: '额外引用',
  temporary: '本轮临时',
  skill_asset: 'Skill 资料',
}

export function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name
}

export function fileSourceLabel(source: string): string {
  return FILE_SOURCE_LABELS[source] ?? source
}

/** Suffix explaining a non-included file status; empty when it was included. */
export function fileStatusHint(status: MessageFileMeta['status']): string {
  if (status === 'skipped') return '（超预算未展开）'
  if (status === 'failed') return '（读取失败）'
  return ''
}

/** Format a tool-chain duration in ms as `1.2s`; empty when unknown. */
export function formatDurationMs(ms: number | null | undefined): string {
  if (!ms || ms <= 0) return ''
  return `${(ms / 1000).toFixed(1)}s`
}

export function chainDuration(message: ChatMessage): string {
  return formatDurationMs(message.metadata?.duration_ms)
}

/** Elapsed seconds label for the in-flight assistant bubble (`12s`). */
export function formatElapsedSeconds(seconds: number): string {
  return `${Math.max(0, Math.trunc(seconds))}s`
}

export function usageLabel(usage: TaskUsage | null | undefined): string | null {
  return usage?.total_tokens ? `${usage.total_tokens} tokens` : null
}

export function messageTools(message: ChatMessage): MessageToolMeta[] {
  return message.metadata?.tools ?? []
}

export function messageFiles(message: ChatMessage): MessageFileMeta[] {
  return message.metadata?.files ?? []
}
