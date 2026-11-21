import type { Page, Route } from '@playwright/test'

const now = new Date().toISOString()
const workspace = {
  id: 'w1',
  name: 'E2E Workspace',
  description: null,
  default_temperature: 0.7,
  default_max_tokens: 4096,
  context_budget_tokens: 32768,
  created_at: now,
  updated_at: now,
}

export interface MockState {
  projects: any[]
  tasks: any[]
  files: any[]
  series: any[]
  artifacts: any[]
  messages: any[]
}

export async function installMockApi(page: Page): Promise<MockState> {
  const state: MockState = {
    projects: [],
    tasks: [],
    files: [],
    series: [],
    artifacts: [],
    messages: [],
  }

  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })

  const projectView = (project: any) => ({
    ...project,
    task_count: state.tasks.filter((task) => task.project_id === project.id).length,
    file_count: state.files.length,
  })

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const method = request.method()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')
    const parts = path.split('/').filter(Boolean)

    // Workspace / models
    if (method === 'GET' && path === '/workspaces') return json(route, [workspace])
    if (method === 'GET' && path === '/models')
      return json(route, [{ provider: 'mock', model: 'mock-chat', label: 'Mock Chat' }])
    if (method === 'GET' && path === '/providers') return json(route, [])
    if (method === 'GET' && path === '/skills') return json(route, [])
    if (method === 'GET' && path === '/stats/overview')
      return json(route, {
        period_days: 7,
        conversation_turns: 3,
        execution_count: 0,
        tokens: { prompt_tokens: 300, completion_tokens: 120, total_tokens: 420 },
        tokens_complete: true,
        daily: Array.from({ length: 7 }, (_, index) => ({
          date: `2026-11-${String(15 + index).padStart(2, '0')}`,
          conversation_turns: index % 3,
          prompt_tokens: index * 40,
          completion_tokens: index * 10,
          total_tokens: index * 50,
        })),
        recent_artifacts: [],
      })

    // Files
    if (method === 'GET' && path === '/files') return json(route, state.files)
    if (method === 'POST' && path === '/files') {
      const file = {
        id: 'f1',
        filename: 'e2e-notes.md',
        file_type: 'md',
        mime_type: 'text/markdown',
        size: 20,
        content_hash: 'hash-f1',
        status: 'active',
        created_at: now,
        updated_at: now,
      }
      state.files = [file]
      return json(route, file, 201)
    }

    // Projects
    if (method === 'GET' && path === '/projects')
      return json(route, state.projects.map(projectView))
    if (method === 'POST' && path === '/projects') {
      const body = request.postDataJSON() as any
      const project = {
        id: 'p1',
        workspace_id: workspace.id,
        name: body.name,
        description: body.description ?? null,
        status: 'active',
        created_at: now,
        updated_at: now,
      }
      state.projects = [project]
      return json(route, projectView(project), 201)
    }
    if (parts[0] === 'projects' && parts[1]) {
      const project = state.projects.find((item) => item.id === parts[1])
      if (!project) return json(route, { error: { code: 'not_found', message: 'no project' } }, 404)
      if (parts[2] === 'files' && method === 'GET')
        return json(route, state.files.map((file) => ({ file, added_at: now, source: 'project' })))
      if (parts[2] === 'artifact-series' && method === 'GET') return json(route, [])
      if (method === 'GET' && parts.length === 2) return json(route, projectView(project))
    }

    // Tasks
    if (method === 'GET' && path === '/tasks') return json(route, state.tasks)
    if (method === 'POST' && path === '/tasks') {
      const body = request.postDataJSON() as any
      const task = {
        id: 't1',
        workspace_id: workspace.id,
        project_id: body.project_id ?? null,
        title: body.title,
        description: body.description ?? null,
        status: 'active',
        model_provider: body.model_provider ?? null,
        model_name: body.model_name ?? null,
        temperature: null,
        max_tokens: null,
        usage: null,
        created_at: now,
        updated_at: now,
      }
      state.tasks = [task]
      return json(route, task, 201)
    }
    if (parts[0] === 'tasks' && parts[1]) {
      const task = state.tasks.find((item) => item.id === parts[1]) ?? state.tasks[0]
      if (!task) return json(route, { error: { code: 'not_found', message: 'no task' } }, 404)
      if (parts[2] === 'files' && method === 'GET')
        return json(route, {
          available: state.files.map((file) => ({ file, source: 'project_inherited' })),
          excluded: [],
          project_file_count: state.files.length,
          task_include_count: 0,
          task_exclude_count: 0,
        })
      if (parts[2] === 'skills' && method === 'GET') return json(route, [])
      if (parts[2] === 'executions' && method === 'GET') return json(route, [])
      if (parts[2] === 'messages' && method === 'GET')
        return json(route, {
          task_id: task.id,
          conversation_id: 'c1',
          messages: state.messages,
          task_usage: null,
        })
      if (parts[2] === 'messages' && method === 'POST') {
        const body = request.postDataJSON() as any
        state.messages.push({
          id: 'm1',
          conversation_id: 'c1',
          role: 'user',
          content: body.content,
          sequence: 1,
          usage: null,
          metadata: { skill: null, files: [] },
          created_at: now,
        })
        state.series = [
          {
            id: 's1',
            task_id: task.id,
            title: 'E2E 系列',
            description: null,
            current_artifact_id: 'a1',
            created_at: now,
            updated_at: now,
          },
        ]
        state.artifacts = [
          {
            id: 'a1',
            series_id: 's1',
            source_execution_id: null,
            source_type: 'chat',
            source_message_id: 'm2',
            version: 1,
            title: 'E2E 成果',
            content_type: 'text/markdown',
            content: '# E2E 成果\n\n这是 Mock 生成的核心闭环成果。',
            storage_key: null,
            created_at: now,
          },
        ]
        state.messages.push({
          id: 'm2',
          conversation_id: 'c1',
          role: 'assistant',
          content: '# E2E 成果\n\n这是 Mock 生成的核心闭环成果。',
          sequence: 2,
          usage: null,
          metadata: {
            skill: null,
            files: [],
            tools: [{ name: 'save_artifact', ok: true, summary: '已保存成果「E2E 成果」v1' }],
            duration_ms: 1200,
            artifacts: 1,
          },
          created_at: now,
        })
        const sse = [
          'event: start',
          'data: {"provider":"mock","model":"mock-chat"}',
          '',
          'event: tool_call',
          'data: {"name":"save_artifact","arguments":{"title":"E2E 成果"}}',
          '',
          'event: tool_result',
          'data: {"name":"save_artifact","ok":true,"summary":"已保存成果「E2E 成果」v1","artifact_id":"a1","execution_id":null}',
          '',
          'event: delta',
          'data: {"text":"# E2E 成果\n\n这是 Mock 生成的核心闭环成果。"}',
          '',
          'event: done',
          'data: {"message_id":"m2","usage":null,"task_usage":null,"tools_enabled":true,"artifacts":["a1"],"executions":[]}',
          '',
        ].join('\n')
        return route.fulfill({
          status: 200,
          headers: {
            'content-type': 'text/event-stream',
            'cache-control': 'no-cache',
          },
          body: sse,
        })
      }
      if (parts[2] === 'artifact-series' && method === 'GET') return json(route, state.series)
      if (method === 'GET' && parts.length === 2) return json(route, task)
    }

    // Artifacts
    if (parts[0] === 'artifact-series' && parts[1] && method === 'GET') {
      const series = state.series.find((item) => item.id === parts[1])
      if (!series) return json(route, { error: { code: 'not_found', message: 'no series' } }, 404)
      return json(route, {
        ...series,
        artifacts: state.artifacts.filter((item) => item.series_id === series.id),
      })
    }
    if (parts[0] === 'artifacts' && parts[1]) {
      const artifact = state.artifacts.find((item) => item.id === parts[1])
      if (!artifact) return json(route, { error: { code: 'not_found', message: 'no artifact' } }, 404)
      if (parts[2] === 'download' && method === 'GET') {
        return route.fulfill({
          status: 200,
          headers: {
            'content-type': 'text/markdown; charset=utf-8',
            'content-disposition': 'attachment; filename="e2e-artifact.md"',
          },
          body: artifact.content,
        })
      }
      if (method === 'DELETE') {
        state.artifacts = state.artifacts.filter((item) => item.id !== parts[1])
        state.series = []
        return route.fulfill({ status: 204, body: '' })
      }
      if (method === 'GET') return json(route, artifact)
    }

    return json(route, { error: { code: 'mock_not_found', message: path } }, 404)
  })

  return state
}
