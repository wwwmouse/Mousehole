# mousehole frontend (Phase 1)

Vue 3 + TypeScript + Vite + Pinia + Vue Router. Desktop-first, single dark theme,
no UI component library and no Markdown dependency.

## Scripts

```bash
npm install
npm run dev        # Vite dev server on :5173, proxies /api -> 127.0.0.1:8000
npm run build      # vue-tsc --noEmit && vite build
npm run preview
npm run typecheck
```

The dev server proxies `/api` to `http://127.0.0.1:8000` (see `vite.config.mjs`).
The API base path used by the client is `/api/v1`.

## Structure

```
src/
  api/
    client.ts        fetch wrapper: base URL, timeout, ApiError normalisation
    endpoints.ts     typed resource functions (workspace/project/task/file)
    types.ts         shared API types (mirrors backend Pydantic schemas)
  components/        AppShell, Toast, Modal, ConfirmDialog, EmptyState,
                     StatusBadge, PageHeader, LoadingState, MarkdownText,
                     FilePickerModal, NewProjectModal, NewTaskModal, AppIcon
  router/index.ts    /, /projects, /projects/:id, /tasks/:id, /library, /settings
  stores/app.ts      workspace + toast + sidebar state (Pinia)
  styles/main.css    tokens + shared primitives (buttons, inputs, cards, chips)
  utils/             formatting, error parsing, minimal Markdown renderer
  views/             Home, Projects, ProjectDetail, Task, Library, Settings, NotFound
```

Phase placeholders are explicit in the UI: Chat/Execution (Phase 2), Artifacts
(Phase 3), Application Settings / model provider (Phase 2). No placeholder data
is faked; unavailable values render as "暂无数据/不可用".

## API contract

All requests go to `/api/v1` and follow the backend error envelope
`{"error":{"code","message","details"}}`; `client.ts` turns it into `ApiError`.
Endpoints used:

- `GET/PATCH /workspaces[/{id}]`
- `GET/POST /projects`, `GET/PATCH /projects/{id}`
- `GET/POST/DELETE /projects/{id}/files[/{file_id}]`
- `GET/POST /tasks`, `GET/PATCH /tasks/{id}`
- `GET/POST /tasks/{id}/files`, `DELETE /tasks/{id}/files/{file_id}`
- `GET/POST /files`, `GET/DELETE /files/{id}`, `GET /files/{id}/content`

## Build environment note

Phase 1 was developed in a Windows sandbox that forbids child processes with
piped stdio, which breaks esbuild (Vite's default transformer) and Vite's
	extit{net use} realpath probe. `vite.config.mjs` probes those capabilities at load
time:

- **Normal machines:** esbuild is available, so the standard Vite toolchain is
  used unchanged (fast path, minification, config bundling).
- **Restricted environments:** it falls back to the TypeScript compiler for
  `.ts`/SFC script transforms, disables minification and dependency
  pre-bundling, neutralises the optional realpath probe, and uses Vite's native
  config loader (hence `--configLoader native` in the package scripts).

This is why the project ships `vite.config.mjs` (not `.ts`): the config has to be
loadable without esbuild in restricted environments. On a normal machine the
resulting `dist/` is functionally equivalent, with unminified output in the
fallback path.
