import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { listWorkspaces, updateWorkspace } from '@/api/endpoints'
import type { Workspace } from '@/api/types'
import { errorDetail, errorMessage } from '@/utils/errors'

export type ToastKind = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  kind: ToastKind
  message: string
  detail: string | null
}

export type WorkspaceState = 'idle' | 'loading' | 'ready' | 'error'

const SIDEBAR_KEY = 'mousehole.sidebar.collapsed'
const TOAST_LIMIT = 5

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(SIDEBAR_KEY) === '1'
  } catch {
    return false
  }
}

function persistCollapsed(value: boolean): void {
  try {
    window.localStorage.setItem(SIDEBAR_KEY, value ? '1' : '0')
  } catch {
    /* localStorage may be unavailable; collapsing still works for this session */
  }
}

export const useAppStore = defineStore('app', () => {
  const workspaces = ref<Workspace[]>([])
  const activeWorkspaceId = ref<string | null>(null)
  const workspaceState = ref<WorkspaceState>('idle')
  const workspaceError = ref<string | null>(null)

  const sidebarCollapsed = ref(readCollapsed())
  const toasts = ref<Toast[]>([])
  let toastSeq = 0

  const currentWorkspace = computed<Workspace | null>(
    () => workspaces.value.find((item) => item.id === activeWorkspaceId.value) ?? null,
  )

  async function loadWorkspace(force = false): Promise<void> {
    if (!force && (workspaceState.value === 'loading' || workspaceState.value === 'ready')) {
      return
    }
    workspaceState.value = 'loading'
    workspaceError.value = null
    try {
      const list = await listWorkspaces()
      workspaces.value = list
      if (!activeWorkspaceId.value || !list.some((item) => item.id === activeWorkspaceId.value)) {
        activeWorkspaceId.value = list[0]?.id ?? null
      }
      workspaceState.value = 'ready'
    } catch (error) {
      workspaceState.value = 'error'
      workspaceError.value = errorMessage(error)
    }
  }

  async function renameWorkspace(name: string): Promise<Workspace> {
    const current = currentWorkspace.value
    if (!current) throw new Error('当前没有可用的工作空间')
    const updated = await updateWorkspace(current.id, { name })
    workspaces.value = workspaces.value.map((item) => (item.id === updated.id ? updated : item))
    return updated
  }

  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
    persistCollapsed(sidebarCollapsed.value)
  }

  function dismissToast(id: number): void {
    toasts.value = toasts.value.filter((toast) => toast.id !== id)
  }

  function notify(kind: ToastKind, message: string, detail: string | null = null): void {
    const id = ++toastSeq
    toasts.value = [...toasts.value, { id, kind, message, detail }].slice(-TOAST_LIMIT)
    const lifetime = kind === 'error' ? 7000 : 4500
    window.setTimeout(() => dismissToast(id), lifetime)
  }

  function notifyError(error: unknown, fallback: string | null = null): void {
    const detail = errorDetail(error) ?? fallback
    notify('error', errorMessage(error), detail)
  }

  return {
    workspaces,
    activeWorkspaceId,
    workspaceState,
    workspaceError,
    sidebarCollapsed,
    toasts,
    currentWorkspace,
    loadWorkspace,
    renameWorkspace,
    toggleSidebar,
    notify,
    notifyError,
    dismissToast,
  }
})
