import type {
  ChatMessage,
  Execution,
  ExecutionDetail,
  ExecutionStep,
  FileItem,
  Project,
  Task,
  TaskAvailableFile,
  TaskFileContext,
} from '@/api/types'

/** Small typed factories so unit tests stay readable without network/mocks. */

export function makeFile(overrides: Partial<FileItem> = {}): FileItem {
  return {
    id: 'file-1',
    filename: 'notes.md',
    file_type: 'md',
    mime_type: 'text/markdown',
    size: 1024,
    content_hash: 'hash-1',
    status: 'active',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    workspace_id: 'workspace-1',
    project_id: null,
    title: 'Task',
    description: null,
    status: 'active',
    model_provider: null,
    model_name: null,
    temperature: null,
    max_tokens: null,
    usage: null,
    last_message_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 'project-1',
    workspace_id: 'workspace-1',
    name: 'Project',
    description: null,
    status: 'active',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    task_count: 0,
    file_count: 0,
    ...overrides,
  }
}

export function makeExecution(overrides: Partial<Execution> = {}): Execution {
  return {
    id: 'execution-1',
    task_id: 'task-1',
    sequence: 1,
    status: 'running',
    skill_id: null,
    skill_name: null,
    model_provider: null,
    model_name: null,
    temperature: null,
    max_tokens: null,
    input_summary: null,
    error_message: null,
    error_code: null,
    usage: null,
    started_at: null,
    completed_at: null,
    created_at: '2025-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makeStep(overrides: Partial<ExecutionStep> = {}): ExecutionStep {
  return {
    id: 'step-1',
    sequence: 1,
    step_type: 'resolve_files',
    name: '解析可用文件',
    status: 'completed',
    input_summary: null,
    output_summary: null,
    started_at: null,
    completed_at: null,
    error_message: null,
    ...overrides,
  }
}

export function makeExecutionDetail(
  overrides: Partial<ExecutionDetail> = {},
): ExecutionDetail {
  return {
    ...makeExecution(),
    steps: [],
    snapshots: [],
    artifact_ids: [],
    ...overrides,
  }
}

export function makeMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'message-1',
    conversation_id: 'conversation-1',
    role: 'assistant',
    content: 'hello',
    sequence: 1,
    usage: null,
    metadata: null,
    created_at: '2025-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makeAvailableFile(
  overrides: Partial<TaskAvailableFile> = {},
): TaskAvailableFile {
  return { file: makeFile(), source: 'project_inherited', ...overrides }
}

export function makeTaskFileContext(
  overrides: Partial<TaskFileContext> = {},
): TaskFileContext {
  return {
    available: [],
    excluded: [],
    project_file_count: 0,
    task_include_count: 0,
    task_exclude_count: 0,
    ...overrides,
  }
}
