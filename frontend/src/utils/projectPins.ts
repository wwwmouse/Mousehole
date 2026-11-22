const STORAGE_KEY = 'mousehole.pinnedProjects'

export function readPinnedProjects(): string[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
  } catch {
    return []
  }
}

export function writePinnedProjects(ids: string[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
  } catch {
    /* ignore persistence failures */
  }
}

export function togglePinnedProject(ids: string[], projectId: string): string[] {
  const next = ids.includes(projectId)
    ? ids.filter((id) => id !== projectId)
    : [...ids, projectId]
  writePinnedProjects(next)
  return next
}
