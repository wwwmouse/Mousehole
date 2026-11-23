import { describe, expect, it } from 'vitest'

import {
  buildFileRows,
  fileRowSourceLabel,
  filterFileRows,
  isInheritedFile,
  partitionTaskFiles,
} from '@/utils/taskFiles'
import {
  makeAvailableFile,
  makeFile,
  makeTaskFileContext,
} from './factories'

describe('isInheritedFile', () => {
  it('treats both project source spellings as inherited', () => {
    expect(isInheritedFile(makeAvailableFile({ source: 'project_inherited' }))).toBe(true)
    expect(isInheritedFile(makeAvailableFile({ source: 'project' }))).toBe(true)
    expect(isInheritedFile(makeAvailableFile({ source: 'task_added' }))).toBe(false)
    expect(isInheritedFile(makeAvailableFile({ source: 'temporary' }))).toBe(false)
  })
})

describe('partitionTaskFiles', () => {
  it('returns empty collections for a missing context', () => {
    expect(partitionTaskFiles(null)).toEqual({
      projectFiles: [],
      extraFiles: [],
      excludedFiles: [],
      totalAvailable: 0,
      pickerExcludedIds: [],
    })
    expect(partitionTaskFiles(undefined).totalAvailable).toBe(0)
  })

  it('splits available files by source and exposes excluded files', () => {
    const inherited = makeAvailableFile({
      file: makeFile({ id: 'f-inherited' }),
      source: 'project_inherited',
    })
    const extra = makeAvailableFile({
      file: makeFile({ id: 'f-extra', filename: 'extra.md' }),
      source: 'task_added',
    })
    const excluded = makeFile({ id: 'f-excluded', filename: 'old.md' })
    const partition = partitionTaskFiles(
      makeTaskFileContext({
        available: [inherited, extra],
        excluded: [excluded],
      }),
    )
    expect(partition.projectFiles).toEqual([inherited])
    expect(partition.extraFiles).toEqual([extra])
    expect(partition.excludedFiles).toEqual([excluded])
    expect(partition.totalAvailable).toBe(2)
    expect(partition.pickerExcludedIds).toEqual(['f-inherited', 'f-extra', 'f-excluded'])
  })
})

describe('file rows', () => {
  const inherited = makeAvailableFile({
    file: makeFile({ id: 'f-inherited' }),
    source: 'project_inherited',
  })
  const extra = makeAvailableFile({
    file: makeFile({ id: 'f-extra' }),
    source: 'task_added',
  })
  const excluded = makeFile({ id: 'f-excluded' })
  const partition = partitionTaskFiles(
    makeTaskFileContext({ available: [inherited, extra], excluded: [excluded] }),
  )

  it('builds rows in inherited / extra / excluded order', () => {
    const rows = buildFileRows(partition)
    expect(rows.map((row) => [row.file.id, row.source])).toEqual([
      ['f-inherited', 'project_inherited'],
      ['f-extra', 'task_added'],
      ['f-excluded', 'excluded'],
    ])
  })

  it('filters rows by source, with all returning everything', () => {
    const rows = buildFileRows(partition)
    expect(filterFileRows(rows, 'all')).toHaveLength(3)
    expect(filterFileRows(rows, 'task_added').map((row) => row.file.id)).toEqual(['f-extra'])
    expect(filterFileRows(rows, 'project_inherited')).toHaveLength(1)
    expect(filterFileRows(rows, 'excluded')).toHaveLength(1)
  })

  it('labels every row source', () => {
    expect(fileRowSourceLabel('project_inherited')).toBe('项目继承')
    expect(fileRowSourceLabel('task_added')).toBe('额外引用')
    expect(fileRowSourceLabel('excluded')).toBe('已排除')
  })
})
