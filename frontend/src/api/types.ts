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
  default_temperature: number | null
  default_max_tokens: number | null
  context_budget_tokens: number | null
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

export interface TaskUsage {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
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
  temperature: number | null
  max_tokens: number | null
  usage: TaskUsage | null
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
  temperature?: number | null
  max_tokens?: number | null
}

export interface UpdateTaskPayload {
  title?: string
  description?: string | null
  status?: TaskStatus
  project_id?: string | null
  model_provider?: string | null
  model_name?: string | null
  temperature?: number | null
  max_tokens?: number | null
}

export interface UpdateWorkspacePayload {
  name?: string
  description?: string | null
  default_temperature?: number | null
  default_max_tokens?: number | null
  context_budget_tokens?: number | null
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

export interface ChatMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  sequence: number
  usage: TaskUsage | null
  created_at: string
}

export interface TaskMessages {
  task_id: string
  conversation_id: string | null
  messages: ChatMessage[]
  task_usage: TaskUsage | null
}

export interface Provider {
  name: string
  kind: string
  base_url: string
  configured: boolean
  masked_key: string
  models: string[]
  default_model: string | null
}

export interface ProviderUpdate {
  api_key?: string
  base_url?: string
  models?: string[]
  default_model?: string | null
}

export interface ProviderTestResult {
  ok: boolean
  message: string
}

export interface ModelInfo {
  provider: string
  model: string
  label: string
}

export type ExecutionStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface ExecutionStep {
  id: string
  sequence: number
  step_type: string
  name: string
  status: string
  input_summary: string | null
  output_summary: string | null
  started_at: string | null
  completed_at: string | null
  error_message: string | null
}

export interface ExecutionSnapshot {
  id: string
  file_id: string
  filename_snapshot: string
  content_hash_snapshot: string
  source_type: string
  usage_mode: string
  used_at: string
}

export interface Skill {
  id: string
  code: string | null
  name: string
  description: string | null
  system_prompt: string
  instruction: string
  output_type: string
  is_builtin: boolean
  created_at: string
  updated_at: string
}

export interface SkillFileInfo {
  file_id: string
  filename: string
  file_type: string
  size: number
  path: string | null
  created_at: string
}

export interface SkillPayload {
  name: string
  description?: string | null
  instruction: string
  system_prompt?: string | null
}

export interface Execution {
  id: string
  task_id: string
  sequence: number
  status: ExecutionStatus
  skill_id: string | null
  skill_name: string | null
  model_provider: string | null
  model_name: string | null
  temperature: number | null
  max_tokens: number | null
  input_summary: string | null
  error_message: string | null
  error_code: string | null
  usage: TaskUsage | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface ExecutionDetail extends Execution {
  steps: ExecutionStep[]
  snapshots: ExecutionSnapshot[]
  artifact_ids: string[]
}

export interface ArtifactSeries {
  id: string
  task_id: string
  title: string
  description: string | null
  current_artifact_id: string | null
  created_at: string
  updated_at: string
}

export interface Artifact {
  id: string
  series_id: string
  source_execution_id: string | null
  source_type: string
  source_message_id: string | null
  version: number
  title: string
  content_type: string
  content: string | null
  storage_key: string | null
  created_at: string
}

export interface ArtifactSeriesDetail extends ArtifactSeries {
  artifacts: Artifact[]
}

/** Normalised backend error envelope: { error: { code, message, details } }. */
export interface ApiErrorPayload {
  error: {
    code: string
    message: string
    details?: unknown
  }
}
