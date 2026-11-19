import { request } from './client'
import type {
  CreateProjectPayload,
  CreateTaskPayload,
  FileContent,
  FileDetail,
  FileItem,
  FileListQuery,
  ModelInfo,
  Project,
  ProjectFile,
  ProjectListQuery,
  Provider,
  ProviderTestResult,
  ProviderUpdate,
  Task,
  TaskFileContext,
  TaskFileMutationPayload,
  TaskListQuery,
  TaskMessages,
  UpdateProjectPayload,
  UpdateTaskPayload,
  UpdateWorkspacePayload,
  Workspace,
} from './types'

/* ---------------------------------- workspace --------------------------------- */

export function listWorkspaces(): Promise<Workspace[]> {
  return request<Workspace[]>('/workspaces')
}

export function getWorkspace(id: string): Promise<Workspace> {
  return request<Workspace>(`/workspaces/${encodeURIComponent(id)}`)
}

export function updateWorkspace(
  id: string,
  payload: UpdateWorkspacePayload,
): Promise<Workspace> {
  return request<Workspace>(`/workspaces/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    json: payload,
  })
}

/* ---------------------------------- project ---------------------------------- */

export function listProjects(query: ProjectListQuery = {}): Promise<Project[]> {
  return request<Project[]>('/projects', { query: { ...query } })
}

export function getProject(id: string): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(id)}`)
}

export function createProject(payload: CreateProjectPayload): Promise<Project> {
  return request<Project>('/projects', { method: 'POST', json: payload })
}

export function updateProject(
  id: string,
  payload: UpdateProjectPayload,
): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    json: payload,
  })
}

export function deleteProject(id: string): Promise<void> {
  return request<void>(`/projects/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function listProjectFiles(projectId: string): Promise<ProjectFile[]> {
  return request<ProjectFile[]>(`/projects/${encodeURIComponent(projectId)}/files`)
}

export function addProjectFile(projectId: string, fileId: string): Promise<ProjectFile> {
  return request<ProjectFile>(`/projects/${encodeURIComponent(projectId)}/files`, {
    method: 'POST',
    json: { file_id: fileId },
  })
}

export function removeProjectFile(projectId: string, fileId: string): Promise<void> {
  return request<void>(
    `/projects/${encodeURIComponent(projectId)}/files/${encodeURIComponent(fileId)}`,
    { method: 'DELETE' },
  )
}

/* ------------------------------------ task ----------------------------------- */

export function listTasks(query: TaskListQuery = {}): Promise<Task[]> {
  return request<Task[]>('/tasks', { query: { ...query } })
}

export function getTask(id: string): Promise<Task> {
  return request<Task>(`/tasks/${encodeURIComponent(id)}`)
}

export function createTask(payload: CreateTaskPayload): Promise<Task> {
  return request<Task>('/tasks', { method: 'POST', json: payload })
}

export function updateTask(id: string, payload: UpdateTaskPayload): Promise<Task> {
  return request<Task>(`/tasks/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    json: payload,
  })
}

export function deleteTask(id: string): Promise<void> {
  return request<void>(`/tasks/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function getTaskFiles(taskId: string): Promise<TaskFileContext> {
  return request<TaskFileContext>(`/tasks/${encodeURIComponent(taskId)}/files`)
}

export function updateTaskFile(
  taskId: string,
  payload: TaskFileMutationPayload,
): Promise<unknown> {
  return request<unknown>(`/tasks/${encodeURIComponent(taskId)}/files`, {
    method: 'POST',
    json: payload,
  })
}

export function removeTaskFileOverride(taskId: string, fileId: string): Promise<void> {
  return request<void>(
    `/tasks/${encodeURIComponent(taskId)}/files/${encodeURIComponent(fileId)}`,
    { method: 'DELETE' },
  )
}

/* ---------------------------------- chat ------------------------------------- */

export function listTaskMessages(taskId: string): Promise<TaskMessages> {
  return request<TaskMessages>(`/tasks/${encodeURIComponent(taskId)}/messages`)
}

/* --------------------------------- providers --------------------------------- */

export function listProviders(): Promise<Provider[]> {
  return request<Provider[]>('/providers')
}

export function updateProvider(name: string, payload: ProviderUpdate): Promise<Provider> {
  return request<Provider>(`/providers/${encodeURIComponent(name)}`, {
    method: 'PUT',
    json: payload,
  })
}

export function testProvider(name: string): Promise<ProviderTestResult> {
  return request<ProviderTestResult>(`/providers/${encodeURIComponent(name)}/test`, {
    method: 'POST',
  })
}

export function listModels(): Promise<ModelInfo[]> {
  return request<ModelInfo[]>('/models')
}

/* ------------------------------------ file ----------------------------------- */

export function listFiles(query: FileListQuery = {}): Promise<FileItem[]> {
  return request<FileItem[]>('/files', { query: { ...query } })
}

export function getFile(id: string): Promise<FileDetail> {
  return request<FileDetail>(`/files/${encodeURIComponent(id)}`)
}

export function uploadFile(file: File): Promise<FileItem> {
  const form = new FormData()
  form.append('file', file)
  return request<FileItem>('/files', { method: 'POST', form })
}

export function getFileContent(
  id: string,
  maxChars = 20_000,
): Promise<FileContent> {
  return request<FileContent>(`/files/${encodeURIComponent(id)}/content`, {
    query: { max_chars: maxChars },
  })
}

export function deleteFile(id: string): Promise<void> {
  return request<void>(`/files/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
