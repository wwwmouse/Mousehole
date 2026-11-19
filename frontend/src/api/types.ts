/**
 * Shared API types for mousehole Phase 1.
 * Field shapes mirror the FastAPI Pydantic schemas in backend/app/modules.
 */

export type ProjectStatus = 'active' | 'archived'
export type TaskStatus = 'active' | 'completed' | 'archived'
export type FileStatus = 'active' | 'deleted'
export type FileOverrideAction = 'include' | 'exclude'

export interface Workspace {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface Project {
  id: string
  workspace_id: string
  name: string
  description: string | null
  status: ProjectStatus
  created_at: string
  updated_at: string
  task_count: number
  file_count: number
}

export interface Task {
  id: string
  workspace_id: string
  project_id: string | null
  title: string
  description: string | null
  status: TaskStatus
  model_provider: string | null
  model_name: string | null
  created_at: string
  updated_at: string
}

export interface FileItem {
  id: string
  filename: string
  file_type: string
  mime_type: string
  size: number
  content_hash: string
  status: FileStatus
  created_at: string
  updated_at: string
}

export interface FileReference {
  kind: string
  id: string
  name: string
}

export interface FileDetail extends FileItem {
  references: FileReference[]
}

export interface FileContent {
  file: FileItem
  text: string
  truncated: boolean
}

export interface ProjectFile {
  file: FileItem
  added_at: string
  source: string
}

export interface TaskAvailableFile {
  file: FileItem
  source: string
}

export interface TaskFileContext {
  available: TaskAvailableFile[]
  excluded: FileItem[]
  project_file_count: number
  task_include_count: number
  task_exclude_count: number
}

export interface CreateProjectPayload {
  workspace_id?: string
  name: string
  description?: string | null
}

export interface UpdateProjectPayload {
  name?: string
  description?: string | null
  status?: ProjectStatus
}

export interface CreateTaskPayload {
  workspace_id?: string
  project_id?: string | null
  title: string
  description?: string | null
  model_provider?: string | null
  model_name?: string | null
}

export interface UpdateTaskPayload {
  title?: string
  description?: string | null
  status?: TaskStatus
  project_id?: string | null
  model_provider?: string | null
  model_name?: string | null
}

export interface UpdateWorkspacePayload {
  name?: string
  description?: string | null
}

export interface ProjectListQuery {
  workspace_id?: string
  status?: ProjectStatus
  limit?: number
  offset?: number
}

export interface TaskListQuery {
  workspace_id?: string
  project_id?: string
  status?: TaskStatus
  limit?: number
  offset?: number
}

export interface FileListQuery {
  search?: string
  file_type?: string
  status?: FileStatus
  limit?: number
  offset?: number
}

export interface TaskFileMutationPayload {
  file_id: string
  action: FileOverrideAction
}

/** Normalised backend error envelope: { error: { code, message, details } }. */
export interface ApiErrorPayload {
  error: {
    code: string
    message: string
    details?: unknown
  }
}
