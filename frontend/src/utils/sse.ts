/**
 * Minimal SSE (text/event-stream) framing helpers shared by the Chat and
 * Execution stream clients. Pure functions only: no network, no DOM, no Vue.
 *
 * The wire format produced by the backend is one block per event:
 *
 *   event: delta\n
 *   data: {"text":"…"}\n
 *   \n
 *
 * Blocks are separated by a blank line (`\n\n`). Data lines are JSON-joined
 * into a single payload. Malformed JSON (or a block without data) is skipped
 * instead of throwing: a broken frame must never crash the stream reader.
 */

export interface SseEvent {
  /** Event name from the `event:` field; defaults to `message`. */
  event: string
  /** Parsed JSON payload from the `data:` line(s). */
  data: Record<string, unknown>
}

export interface SseParserOptions {
  /**
   * Drop blocks that start with a comment (`: keepalive`). The execution
   * stream sends keepalives and ignores them; the chat stream has no comments.
   */
  skipComments?: boolean
}

export interface SseParser {
  /** Feed a decoded chunk; returns every complete event it contains. */
  feed(chunk: string): SseEvent[]
  /** Flush the trailing buffer (a final event without a blank line). */
  flush(): SseEvent[]
}

export function parseSseBlock(
  raw: string,
  options: SseParserOptions = {},
): SseEvent | null {
  if (!raw.trim()) return null
  if (options.skipComments && raw.startsWith(':')) return null
  const lines = raw.split('\n')
  let event = 'message'
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (dataLines.length === 0) return null
  try {
    return { event, data: JSON.parse(dataLines.join('\n')) as Record<string, unknown> }
  } catch {
    return null
  }
}

export function createSseParser(options: SseParserOptions = {}): SseParser {
  let buffer = ''

  function parse(raw: string): SseEvent | null {
    return parseSseBlock(raw, options)
  }

  return {
    feed(chunk: string): SseEvent[] {
      buffer += chunk
      const events: SseEvent[] = []
      let index = buffer.indexOf('\n\n')
      while (index >= 0) {
        const raw = buffer.slice(0, index)
        buffer = buffer.slice(index + 2)
        const parsed = parse(raw)
        if (parsed) events.push(parsed)
        index = buffer.indexOf('\n\n')
      }
      return events
    },
    flush(): SseEvent[] {
      const raw = buffer
      buffer = ''
      const parsed = parse(raw)
      return parsed ? [parsed] : []
    },
  }
}
