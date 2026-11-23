import { ref } from 'vue'

import {
  streamTaskChat,
  type ChatPayload,
  type ChatStreamDone,
  type ChatStreamEvent,
  type ChatStreamHandlers,
  type ChatStreamStart,
  type ChatToolResult,
} from '@/api/chat'
import type { TaskUsage } from '@/api/types'
import { errorMessage } from '@/utils/errors'

export type ChatToolStatus = 'running' | 'ok' | 'error'

export interface ChatToolEvent {
  name: string
  status: ChatToolStatus
  summary: string
}

/**
 * Everything the UI needs while one assistant turn is streaming.
 * Kept as a plain object so it can be reduced by pure functions in tests.
 */
export interface ChatStreamState {
  thinking: boolean
  streamText: string
  toolEvents: ChatToolEvent[]
  error: string | null
  started: ChatStreamStart | null
  messageId: string | null
  messageUsage: TaskUsage | null
  taskUsage: TaskUsage | null
  artifacts: string[]
  executions: string[]
  /** A `done` event was received. */
  done: boolean
  /** A stream/protocol error was received (mid-stream error event or HTTP). */
  failed: boolean
}

export type ChatStreamOutcome = 'done' | 'error' | 'aborted'

/** Injected for tests; defaults to the real fetch-based client. */
export type ChatStreamRunner = (
  taskId: string,
  payload: ChatPayload,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
) => Promise<void>

export interface UseChatStreamOptions {
  /** Side effects (usage refresh, artifacts, run card…) on a successful turn. */
  onDone?: (data: ChatStreamDone) => void
  runner?: ChatStreamRunner
}

export function createChatStreamState(): ChatStreamState {
  return {
    thinking: false,
    streamText: '',
    toolEvents: [],
    error: null,
    started: null,
    messageId: null,
    messageUsage: null,
    taskUsage: null,
    artifacts: [],
    executions: [],
    done: false,
    failed: false,
  }
}

/** Attach a tool result to the most recent still-running call with that name. */
export function applyToolResult(
  events: readonly ChatToolEvent[],
  result: ChatToolResult,
): ChatToolEvent[] {
  let index = -1
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (events[i].name === result.name && events[i].status === 'running') {
      index = i
      break
    }
  }
  if (index === -1) return events.map((event) => ({ ...event }))
  return events.map((event, i) =>
    i === index
      ? { ...event, status: result.ok ? ('ok' as const) : ('error' as const), summary: result.summary }
      : { ...event },
  )
}

/** Pure state transition for one normalised chat stream event. */
export function reduceChatStream(
  state: ChatStreamState,
  event: ChatStreamEvent,
): ChatStreamState {
  switch (event.type) {
    case 'start':
      return { ...state, started: event.data }
    case 'delta':
      return { ...state, thinking: false, streamText: state.streamText + event.text }
    case 'thinking':
      return { ...state, thinking: true }
    case 'tool_call':
      return {
        ...state,
        toolEvents: [
          ...state.toolEvents,
          { name: event.call.name, status: 'running', summary: '' },
        ],
      }
    case 'tool_result':
      return { ...state, toolEvents: applyToolResult(state.toolEvents, event.result) }
    case 'error':
      return { ...state, thinking: false, failed: true, error: event.error.message }
    case 'done':
      return {
        ...state,
        thinking: false,
        done: true,
        messageId: event.data.message_id || state.messageId,
        messageUsage: event.data.usage,
        taskUsage: event.data.task_usage,
        artifacts: event.data.artifacts,
        executions: event.data.executions,
      }
    default:
      return state
  }
}

/** Clear transient flags once the stream finished (success, error or abort). */
export function finishChatStream(state: ChatStreamState): ChatStreamState {
  return { ...state, thinking: false }
}

export function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'name' in error &&
    (error as { name?: unknown }).name === 'AbortError'
  )
}

/**
 * Chat stream state machine: owns the in-flight refs + elapsed timer and maps
 * `streamTaskChat` events through `reduceChatStream`.
 */
export function useChatStream(options: UseChatStreamOptions = {}) {
  const sending = ref(false)
  const elapsed = ref(0)
  const thinking = ref(false)
  const streamText = ref('')
  const toolEvents = ref<ChatToolEvent[]>([])
  const error = ref<string | null>(null)
  const started = ref<ChatStreamStart | null>(null)
  const messageId = ref<string | null>(null)
  const messageUsage = ref<TaskUsage | null>(null)
  const taskUsage = ref<TaskUsage | null>(null)
  const artifacts = ref<string[]>([])
  const executions = ref<string[]>([])
  const done = ref(false)
  const failed = ref(false)

  let timer: ReturnType<typeof setInterval> | null = null
  let controller: AbortController | null = null

  const runner: ChatStreamRunner = options.runner ?? streamTaskChat

  function snapshot(): ChatStreamState {
    return {
      thinking: thinking.value,
      streamText: streamText.value,
      toolEvents: toolEvents.value,
      error: error.value,
      started: started.value,
      messageId: messageId.value,
      messageUsage: messageUsage.value,
      taskUsage: taskUsage.value,
      artifacts: artifacts.value,
      executions: executions.value,
      done: done.value,
      failed: failed.value,
    }
  }

  function writeState(next: ChatStreamState): void {
    thinking.value = next.thinking
    streamText.value = next.streamText
    toolEvents.value = next.toolEvents
    error.value = next.error
    started.value = next.started
    messageId.value = next.messageId
    messageUsage.value = next.messageUsage
    taskUsage.value = next.taskUsage
    artifacts.value = next.artifacts
    executions.value = next.executions
    done.value = next.done
    failed.value = next.failed
  }

  function stopTimer(): void {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function startTimer(): void {
    stopTimer()
    timer = setInterval(() => {
      elapsed.value += 1
    }, 1000)
  }

  /** Reset to a clean state (called before every send). */
  function begin(): void {
    writeState(createChatStreamState())
    elapsed.value = 0
    sending.value = true
    startTimer()
  }

  /** Show an error without starting a stream (e.g. no model configured). */
  function setError(message: string): void {
    writeState({ ...snapshot(), error: message, failed: true })
  }

  function applyEvent(event: ChatStreamEvent): void {
    writeState(reduceChatStream(snapshot(), event))
    if (event.type === 'done') options.onDone?.(event.data)
  }

  async function run(taskId: string, payload: ChatPayload): Promise<ChatStreamOutcome> {
    controller = new AbortController()
    let outcome: ChatStreamOutcome = 'done'
    try {
      await runner(
        taskId,
        payload,
        { onEvent: (event) => applyEvent(event) },
        controller.signal,
      )
    } catch (err) {
      if (isAbortError(err)) {
        outcome = 'aborted'
      } else {
        outcome = 'error'
        applyEvent({ type: 'error', error: { code: 'http_error', message: errorMessage(err) } })
      }
    } finally {
      sending.value = false
      writeState(finishChatStream(snapshot()))
      stopTimer()
      controller = null
    }
    if (outcome === 'done' && failed.value) outcome = 'error'
    return outcome
  }

  function stop(): void {
    controller?.abort()
  }

  function dispose(): void {
    stopTimer()
    controller = null
  }

  return {
    sending,
    elapsed,
    thinking,
    streamText,
    toolEvents,
    error,
    started,
    messageId,
    messageUsage,
    taskUsage,
    artifacts,
    executions,
    done,
    failed,
    begin,
    setError,
    applyEvent,
    run,
    stop,
    dispose,
  }
}
