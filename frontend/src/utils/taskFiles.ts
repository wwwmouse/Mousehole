import type { FileItem, TaskAvailableFile, TaskFileContext } from '@/api/types'

/** Classification shown in the Task Settings file list. */
export type FileRowSource = 'project_inherited' | 'task_added' | 'excluded'

export type FileFilter = 'all' | FileRowSource

export interface FileRow {
  file: FileItem
  source: FileRowSource
}

export interface TaskFilePartition {
  projectFiles: TaskAvailableFile[]
  extraFiles: TaskAvailableFile[]
  excludedFiles: FileItem[]
  totalAvailable: number
  /** Library ids that must not be offered again in the picker. */
  pickerExcludedIds: string[]
}

// Backend may label inherited files "project_inherited" (current contract) or
// the shorter "project"; treat both as project-inherited so the UI never
// misclassifies a file.
export function isInheritedFile(item: TaskAvailableFile): boolean {
  return item.source === 'project' || item.source === 'project_inherited'
}

export function partitionTaskFiles(
  context: TaskFileContext | null | undefined,
): TaskFilePartition {
  const available = context?.available ?? []
  const excluded = context?.excluded ?? []
  return {
    projectFiles: available.filter(isInheritedFile),
    extraFiles: available.filter((item) => !isInheritedFile(item)),
    excludedFiles: excluded,
    totalAvailable: available.length,
    pickerExcludedIds: [
      ...available.map((item) => item.file.id),
      ...excluded.map((file) => file.id),
    ],
  }
}

export function buildFileRows(partition: TaskFilePartition): FileRow[] {
  return [
    ...partition.projectFiles.map((item) => ({
      file: item.file,
      source: 'project_inherited' as const,
    })),
    ...partition.extraFiles.map((item) => ({
      file: item.file,
      source: 'task_added' as const,
    })),
    ...partition.excludedFiles.map((file) => ({
      file,
      source: 'excluded' as const,
    })),
  ]
}

export function filterFileRows(rows: FileRow[], filter: FileFilter): FileRow[] {
  return filter === 'all' ? rows : rows.filter((row) => row.source === filter)
}

export function fileRowSourceLabel(source: FileRowSource): string {
  if (source === 'project_inherited') return '项目继承'
  if (source === 'task_added') return '额外引用'
  return '已排除'
}
