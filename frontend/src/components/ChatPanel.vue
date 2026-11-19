<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import LoadingState from '@/components/LoadingState.vue'
import MarkdownText from '@/components/MarkdownText.vue'
import { streamTaskChat } from '@/api/chat'
import { listTaskMessages } from '@/api/endpoints'
import type { ChatMessage, TaskUsage } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'

const props = defineProps<{ taskId: string; hasModel: boolean }>()
const emit = defineEmits<{ 'usage-updated': [usage: TaskUsage | null] }>()

const app = useAppStore()

const messages = ref<ChatMessage[]>([])
const taskUsage = ref<TaskUsage | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const input = ref('')
const sending = ref(false)
const streamText = ref('')
const streamError = ref<string | null>(null)
const listRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
let controller: AbortController | null = null

function usageLabel(usage: TaskUsage | null): string | null {
  if (!usage?.total_tokens) return null
  return `${usage.total_tokens} tokens`
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const data = await listTaskMessages(props.taskId)
    messages.value = data.messages
    taskUsage.value = data.task_usage
    emit('usage-updated', data.task_usage)
    await scrollToBottom()
  } catch (error) {
    loadError.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}

function resizeInput(): void {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

async function send(): Promise<void> {
  const content = input.value.trim()
  if (!content || sending.value) return
  if (!props.hasModel) {
    streamError.value =
      '尚未配置可用模型：请先在 Settings 配置 DeepSeek API Key 或启用 Ollama，再在 Task Settings 选择模型。'
    return
  }

  input.value = ''
  resizeInput()
  sending.value = true
  streamError.value = null
  streamText.value = ''

  messages.value = [
    ...messages.value,
    {
      id: `pending-${Date.now()}`,
      conversation_id: '',
      role: 'user',
      content,
      sequence: 0,
      usage: null,
      created_at: new Date().toISOString(),
    },
  ]
  await scrollToBottom()

  controller = new AbortController()
  let failed = false
  try {
    await streamTaskChat(
      props.taskId,
      { content },
      {
        onDelta: (text) => {
          streamText.value += text
          void scrollToBottom()
        },
        onError: (error) => {
          failed = true
          streamError.value = error.message
        },
        onDone: (data) => {
          taskUsage.value = data.task_usage as TaskUsage | null
        },
      },
      controller.signal,
    )
  } catch (error) {
    const aborted =
      error instanceof DOMException && error.name === 'AbortError'
    if (aborted) {
      app.notify('info', '已停止生成')
    } else {
      failed = true
      streamError.value = errorMessage(error)
    }
  } finally {
    sending.value = false
    streamText.value = ''
    controller = null
    await load()
    if (failed) app.notify('error', '对话未完成，请查看错误信息')
  }
}

function stop(): void {
  controller?.abort()
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    void send()
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="chat-panel">
    <div v-if="taskUsage && taskUsage.total_tokens" class="chat-usage">
      <span class="chat-usage__total">
        本任务累计 <strong>{{ taskUsage.total_tokens }}</strong> tokens
      </span>
      <span class="chat-usage__detail">
        prompt {{ taskUsage.prompt_tokens ?? 0 }} · completion {{ taskUsage.completion_tokens ?? 0 }}
      </span>
    </div>

    <div v-if="!hasModel" class="notice notice--warning">
      <AppIcon name="alert" :size="15" />
      <span>
        尚未配置可用模型：请先在 Settings 中配置 DeepSeek API Key 或启用 Ollama，然后在 Task 的
        Settings 里选择模型。
      </span>
    </div>

    <div ref="listRef" class="chat-thread">
      <LoadingState v-if="loading" compact label="正在加载对话…" />

      <div v-else-if="loadError" class="panel panel--error">
        <AppIcon name="alert" :size="16" />
        <div>
          <p class="panel--error__title">对话加载失败</p>
          <p class="panel--error__desc">{{ loadError }}</p>
        </div>
        <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
      </div>

      <div v-else-if="messages.length === 0 && !sending" class="chat-empty">
        <AppIcon name="sparkles" :size="22" />
        <p class="chat-empty__title">开始对话</p>
        <p class="chat-empty__desc">
          普通聊天记录会保存到 Conversation；正式的多文档执行与 Artifact 将在 Phase 3 提供。
        </p>
      </div>

      <div v-else class="chat-messages">
        <article
          v-for="message in messages"
          :key="message.id"
          class="chat-message"
          :class="`chat-message--${message.role}`"
        >
          <header class="chat-message__head">
            <span class="chat-message__role">{{ message.role === 'user' ? 'You' : 'Assistant' }}</span>
            <span v-if="usageLabel(message.usage)" class="chat-message__usage">
              {{ usageLabel(message.usage) }}
            </span>
          </header>
          <div class="chat-message__body">
            <MarkdownText v-if="message.role === 'assistant'" :text="message.content" />
            <p v-else class="chat-message__text">{{ message.content }}</p>
          </div>
        </article>

        <article v-if="sending" class="chat-message chat-message--assistant">
          <header class="chat-message__head">
            <span class="chat-message__role">Assistant</span>
            <span class="spinner spinner--sm" aria-hidden="true" />
          </header>
          <div class="chat-message__body">
            <MarkdownText v-if="streamText" :text="streamText" />
            <p v-else class="chat-message__placeholder">正在生成…</p>
          </div>
        </article>
      </div>
    </div>

    <div v-if="streamError" class="panel panel--error chat-error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">本次对话失败</p>
        <p class="panel--error__desc">{{ streamError }}</p>
      </div>
    </div>

    <div class="composer">
      <div class="composer__box">
        <textarea
          ref="inputRef"
          v-model="input"
          class="composer__input"
          rows="2"
          :placeholder="hasModel ? '输入消息…（Ctrl+Enter 发送）' : '请先配置模型'"
          :disabled="sending"
          aria-label="对话输入框"
          @input="resizeInput"
          @keydown="onKeydown"
        />
        <div class="composer__bar">
          <span class="composer__hint">对话会保存到本 Task；不会伪造 AI 回复。</span>
          <button v-if="sending" type="button" class="btn btn--ghost btn--sm" @click="stop">
            停止
          </button>
          <button
            v-else
            type="button"
            class="btn btn--primary btn--sm"
            :disabled="!input.trim() || !hasModel"
            @click="send"
          >
            <AppIcon name="send" :size="14" />
            发送
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 420px;
}

.chat-thread {
  flex: 1;
  min-height: 280px;
  max-height: 60vh;
  overflow-y: auto;
  padding: 4px;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 56px 24px;
  color: var(--text-muted);
  text-align: center;
}

.chat-empty__title {
  margin: 0;
  color: var(--text);
  font-size: 15px;
  font-weight: 600;
}

.chat-empty__desc {
  margin: 0;
  max-width: 460px;
  font-size: 12.5px;
  line-height: 1.7;
}

.chat-messages {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chat-message {
  max-width: 92%;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-raised);
}

.chat-message--user {
  align-self: flex-end;
  background: var(--accent-soft);
  border-color: var(--accent-border);
}

.chat-message--assistant {
  align-self: flex-start;
}

.chat-message__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.chat-message__role {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-faint);
}

.chat-message__usage {
  margin-left: auto;
  padding: 1px 7px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 10.5px;
  color: var(--text-muted);
}

.chat-message__body {
  min-width: 0;
}

.chat-message__text {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--text);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.chat-message__placeholder {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-muted);
}

.chat-error {
  margin: 0;
}

.composer__box {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-subtle);
  padding: 10px;
}

.composer__box:focus-within {
  border-color: var(--accent-border);
}

.composer__input {
  width: 100%;
  min-height: 44px;
  max-height: 160px;
  padding: 4px 2px;
  border: none;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 13.5px;
  line-height: 1.7;
  resize: none;
  outline: none;
}

.composer__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 6px;
  border-top: 1px solid var(--border);
}

.composer__hint {
  font-size: 11px;
  color: var(--text-faint);
}

.chat-usage {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  font-size: 12px;
  color: var(--text-muted);
}

.chat-usage__total strong {
  color: var(--text);
  font-size: 13px;
}

.chat-usage__detail {
  font-size: 11px;
  color: var(--text-faint);
}

.notice--warning {
  border-color: var(--warning-soft);
  color: var(--warning);
}
</style>
