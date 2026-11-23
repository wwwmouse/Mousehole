import { describe, expect, it } from 'vitest'

import { createSseParser, parseSseBlock } from '@/utils/sse'

function block(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

describe('parseSseBlock', () => {
  it('parses an event name and its JSON payload', () => {
    expect(parseSseBlock('event: delta\ndata: {"text":"你好"}')).toEqual({
      event: 'delta',
      data: { text: '你好' },
    })
  })

  it('defaults the event name to message', () => {
    expect(parseSseBlock('data: {"ok":true}')).toEqual({
      event: 'message',
      data: { ok: true },
    })
  })

  it('joins multiple data lines before parsing JSON', () => {
    expect(parseSseBlock('event: done\ndata: {"a":1,\ndata: "b":2}')).toEqual({
      event: 'done',
      data: { a: 1, b: 2 },
    })
  })

  it('returns null for malformed JSON and for blocks without data', () => {
    expect(parseSseBlock('event: delta\ndata: {oops')).toBeNull()
    expect(parseSseBlock('event: thinking')).toBeNull()
    expect(parseSseBlock('   ')).toBeNull()
  })

  it('skips comment blocks only when asked (keepalive)', () => {
    expect(parseSseBlock(': keepalive')).toBeNull()
    expect(parseSseBlock(': keepalive', { skipComments: true })).toBeNull()
    // A block that mixes a comment with data still parses by default.
    expect(parseSseBlock(': note\ndata: {"ok":1}')).toEqual({
      event: 'message',
      data: { ok: 1 },
    })
  })
})

describe('createSseParser', () => {
  it('emits every complete block found in one chunk', () => {
    const parser = createSseParser()
    const events = parser.feed(block('delta', { text: 'a' }) + block('delta', { text: 'b' }))
    expect(events).toEqual([
      { event: 'delta', data: { text: 'a' } },
      { event: 'delta', data: { text: 'b' } },
    ])
  })

  it('buffers a block split across chunks', () => {
    const parser = createSseParser()
    expect(parser.feed('event: delta\ndata: {"text":"he')).toEqual([])
    expect(parser.feed('llo"}\n\n')).toEqual([
      { event: 'delta', data: { text: 'hello' } },
    ])
  })

  it('holds back an unterminated block until flush', () => {
    const parser = createSseParser()
    expect(parser.feed('event: done\ndata: {"message_id":"m1"}')).toEqual([])
    expect(parser.flush()).toEqual([
      { event: 'done', data: { message_id: 'm1' } },
    ])
    expect(parser.flush()).toEqual([])
  })

  it('drops a malformed block but keeps later well-formed ones', () => {
    const parser = createSseParser()
    const events = parser.feed(
      'event: delta\ndata: {broken\n\n' + block('delta', { text: 'ok' }),
    )
    expect(events).toEqual([{ event: 'delta', data: { text: 'ok' } }])
  })

  it('skips keepalive comments with skipComments', () => {
    const parser = createSseParser({ skipComments: true })
    expect(parser.feed(': keepalive\n\n' + block('step.started', { id: 's1' }))).toEqual([
      { event: 'step.started', data: { id: 's1' } },
    ])
  })
})
