import { describe, expect, it } from 'vitest'

import { buildTaskNavigation } from '@/utils/taskNav'
import { makeProject, makeTask } from './factories'

describe('buildTaskNavigation', () => {
  it('separates global tasks from project groups', () => {
    const tasks = [
      makeTask({ id: 'global-1', project_id: null }),
      makeTask({ id: 'p1-task', project_id: 'p1' }),
      makeTask({ id: 'global-2', project_id: null }),
    ]
    const navigation = buildTaskNavigation(tasks, [makeProject({ id: 'p1', name: 'Alpha' })])
    expect(navigation.globalTasks.map((item) => item.id)).toEqual(['global-1', 'global-2'])
    expect(navigation.projectGroups).toHaveLength(1)
    expect(navigation.projectGroups[0]).toMatchObject({
      projectId: 'p1',
      projectName: 'Alpha',
    })
    expect(navigation.projectGroups[0].tasks.map((item) => item.id)).toEqual(['p1-task'])
  })

  it('falls back to a generic name for unknown projects', () => {
    const navigation = buildTaskNavigation(
      [makeTask({ id: 't1', project_id: 'missing' })],
      [],
    )
    expect(navigation.projectGroups[0].projectName).toBe('关联 Project')
  })

  it('sorts pinned projects first, then by Chinese name', () => {
    const tasks = [
      makeTask({ id: 't-b', project_id: 'p-beta' }),
      makeTask({ id: 't-a', project_id: 'p-alpha' }),
      makeTask({ id: 't-z', project_id: 'p-zeta' }),
    ]
    const projects = [
      makeProject({ id: 'p-beta', name: 'Beta' }),
      makeProject({ id: 'p-alpha', name: 'Alpha' }),
      makeProject({ id: 'p-zeta', name: 'Zeta' }),
    ]
    const sorted = buildTaskNavigation(tasks, projects)
    expect(sorted.projectGroups.map((group) => group.projectName)).toEqual([
      'Alpha',
      'Beta',
      'Zeta',
    ])

    const pinned = buildTaskNavigation(tasks, projects, ['p-zeta'])
    expect(pinned.projectGroups.map((group) => group.projectName)).toEqual([
      'Zeta',
      'Alpha',
      'Beta',
    ])
  })

  it('handles empty input', () => {
    expect(buildTaskNavigation([], [])).toEqual({ globalTasks: [], projectGroups: [] })
  })
})
