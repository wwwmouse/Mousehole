import { request } from './client'
import type {
  Artifact,
  ArtifactSeries,
  ArtifactSeriesDetail,
  ConversationContext,
  CreateProjectPayload,
  CreateTaskPayload,
  FileContent,
  FileDetail,
  FileItem,
  FilePages,
  Execution,
  ExecutionDetail,
  FileListQuery,
  ModelInfo,
  OcrJob,
  Project,
  ProjectFile,
  ProjectListQuery,
  Provider,
  ProviderTestResult,
  ProviderUpdate,
  Skill,
  SkillFileInfo,
  StatsOverview,
  SkillPayload,
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

export function uploadProjectFile(
  projectId: string,
  file: File,
): Promise<ProjectFile> {
  const form = new FormData()
  form.append('file', file)
  return request<ProjectFile>(
    `/projects/${encodeURIComponent(projectId)}/files/upload`,
    { method: 'POST', form },
  )
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

export function setConversationContext(
  taskId: string,
  cleared: boolean,
): Promise<ConversationContext> {
  return request<ConversationContext>(
    `/tasks/${encodeURIComponent(taskId)}/messages/context`,
    { method: 'PATCH', json: { cleared } },
  )
}

/* -------------------------------- executions --------------------------------- */

export function createExecution(
  taskId: string,
  skillId?: string,
): Promise<Execution> {
  return request<Execution>(`/tasks/${encodeURIComponent(taskId)}/executions`, {
    method: 'POST',
    json: skillId ? { skill_id: skillId } : undefined,
  })
}

export function listSkills(): Promise<Skill[]> {
  return request<Skill[]>('/skills')
}

export function createSkill(payload: SkillPayload): Promise<Skill> {
  return request<Skill>('/skills', { method: 'POST', json: payload })
}

export function updateSkill(
  skillId: string,
  payload: Partial<SkillPayload>,
): Promise<Skill> {
  return request<Skill>(`/skills/${encodeURIComponent(skillId)}`, {
    method: 'PATCH',
    json: payload,
  })
}

export function deleteSkill(skillId: string): Promise<void> {
  return request<void>(`/skills/${encodeURIComponent(skillId)}`, {
    method: 'DELETE',
  })
}

export function listSkillFiles(skillId: string): Promise<SkillFileInfo[]> {
  return request<SkillFileInfo[]>(
    `/skills/${encodeURIComponent(skillId)}/files`,
  )
}

export function addSkillFile(
  skillId: string,
  fileId: string,
  path?: string,
): Promise<SkillFileInfo> {
  return request<SkillFileInfo>(`/skills/${encodeURIComponent(skillId)}/files`, {
    method: 'POST',
    json: { file_id: fileId, path: path ?? null },
  })
}

export function removeSkillFile(
  skillId: string,
  fileId: string,
): Promise<void> {
  return request<void>(
    `/skills/${encodeURIComponent(skillId)}/files/${encodeURIComponent(fileId)}`,
    { method: 'DELETE' },
  )
}

export function listTaskSkills(taskId: string): Promise<Skill[]> {
  return request<Skill[]>(`/tasks/${encodeURIComponent(taskId)}/skills`)
}

export function addTaskSkill(taskId: string, skillId: string): Promise<Skill> {
  return request<Skill>(`/tasks/${encodeURIComponent(taskId)}/skills`, {
    method: 'POST',
    json: { skill_id: skillId },
  })
}

export function removeTaskSkill(
  taskId: string,
  skillId: string,
): Promise<void> {
  return request<void>(
    `/tasks/${encodeURIComponent(taskId)}/skills/${encodeURIComponent(skillId)}`,
    { method: 'DELETE' },
  )
}

export function listExecutions(taskId: string): Promise<Execution[]> {
  return request<Execution[]>(`/tasks/${encodeURIComponent(taskId)}/executions`)
}

export function getExecution(executionId: string): Promise<ExecutionDetail> {
  return request<ExecutionDetail>(
    `/executions/${encodeURIComponent(executionId)}`,
  )
}

export function cancelExecution(executionId: string): Promise<Execution> {
  return request<Execution>(
    `/executions/${encodeURIComponent(executionId)}/cancel`,
    { method: 'POST' },
  )
}

/* --------------------------------- artifacts ---------------------------------- */

export function listArtifactSeries(taskId: string): Promise<ArtifactSeries[]> {
  return request<ArtifactSeries[]>(
    `/tasks/${encodeURIComponent(taskId)}/artifact-series`,
  )
}

export function listProjectArtifactSeries(
  projectId: string,
): Promise<ArtifactSeries[]> {
  return request<ArtifactSeries[]>(
    `/projects/${encodeURIComponent(projectId)}/artifact-series`,
  )
}

export function getArtifactSeries(
  seriesId: string,
): Promise<ArtifactSeriesDetail> {
  return request<ArtifactSeriesDetail>(
    `/artifact-series/${encodeURIComponent(seriesId)}`,
  )
}

export function renameArtifactSeries(
  seriesId: string,
  title: string,
): Promise<ArtifactSeries> {
  return request<ArtifactSeries>(
    `/artifact-series/${encodeURIComponent(seriesId)}`,
    { method: 'PATCH', json: { title } },
  )
}

export function getArtifact(artifactId: string): Promise<Artifact> {
  return request<Artifact>(`/artifacts/${encodeURIComponent(artifactId)}`)
}

export function deleteArtifact(artifactId: string): Promise<void> {
  return request<void>(`/artifacts/${encodeURIComponent(artifactId)}`, {
    method: 'DELETE',
  })
}

export function exportArtifactToLibrary(artifactId: string): Promise<FileItem> {
  return request<FileItem>(
    `/artifacts/${encodeURIComponent(artifactId)}/to-library`,
    { method: 'POST' },
  )
}

export function artifactDownloadUrl(artifactId: string): string {
  return `/api/v1/artifacts/${encodeURIComponent(artifactId)}/download`
}

export function fileRawUrl(fileId: string, page?: number): string {
  const base = `/api/v1/files/${encodeURIComponent(fileId)}/raw`
  return page && page > 0 ? `${base}#page=${page}` : base
}

export function startFileOcr(fileId: string): Promise<OcrJob> {
  return request<OcrJob>(`/files/${encodeURIComponent(fileId)}/ocr`, {
    method: 'POST',
  })
}

export function getFileOcr(fileId: string): Promise<OcrJob | null> {
  return request<OcrJob | null>(`/files/${encodeURIComponent(fileId)}/ocr`)
}

export function listFilePages(
  fileId: string,
  offset = 0,
  limit = 200,
): Promise<FilePages> {
  return request<FilePages>(`/files/${encodeURIComponent(fileId)}/pages`, {
    query: { offset, limit },
  })
}

/* ---------------------------------- stats ------------------------------------ */

export function getStatsOverview(days = 7): Promise<StatsOverview> {
  return request<StatsOverview>(`/stats/overview?days=${days}`)
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

export function uploadTaskTemporaryFile(
  taskId: string,
  file: File,
): Promise<FileItem> {
  const form = new FormData()
  form.append('file', file)
  return request<FileItem>(
    `/tasks/${encodeURIComponent(taskId)}/files/upload`,
    { method: 'POST', form },
  )
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
