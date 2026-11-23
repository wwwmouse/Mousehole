import type { Project, Task } from '@/api/types'

export interface TaskNavGroup {
  projectId: string
  projectName: string
  tasks: Task[]
}

export interface TaskNavigation {
  /** Tasks that do not belong to a Project. */
  globalTasks: Task[]
  /** Project groups, pinned projects first, then by project name. */
  projectGroups: TaskNavGroup[]
}

/**
 * Build the Task page side navigation: global tasks plus one group per
 * Project. Pinned projects sort first; remaining groups sort by name (zh-CN).
 */
export function buildTaskNavigation(
  tasks: readonly Task[],
  projects: readonly Project[],
  pinnedProjectIds: readonly string[] = [],
): TaskNavigation {
  const globalTasks: Task[] = []
  const groups = new Map<string, Task[]>()
  for (const item of tasks) {
    if (!item.project_id) {
      globalTasks.push(item)
      continue
    }
    const list = groups.get(item.project_id) ?? []
    list.push(item)
    groups.set(item.project_id, list)
  }

  const names = new Map(projects.map((item) => [item.id, item.name]))
  const pinned = new Set(pinnedProjectIds)
  const projectGroups = Array.from(groups.entries())
    .map(([projectId, groupedTasks]) => ({
      projectId,
      projectName: names.get(projectId) ?? '关联 Project',
      tasks: groupedTasks,
    }))
    .sort((a, b) => {
      const aPinned = pinned.has(a.projectId)
      const bPinned = pinned.has(b.projectId)
      if (aPinned !== bPinned) return aPinned ? -1 : 1
      return a.projectName.localeCompare(b.projectName, 'zh-CN')
    })

  return { globalTasks, projectGroups }
}
