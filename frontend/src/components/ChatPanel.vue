<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import LoadingState from '@/components/LoadingState.vue'
import MarkdownText from '@/components/MarkdownText.vue'
import ModelControls from '@/components/ModelControls.vue'
import RunProgress from '@/components/RunProgress.vue'
import { streamTaskChat } from '@/api/chat'
import {
  getArtifact,
  listSkills,
  listTaskMessages,
  removeTaskFileOverride,
  uploadTaskTemporaryFile,
} from '@/api/endpoints'
import type {
  Artifact,
  ChatMessage,
  ModelInfo,
  Skill,
  Task,
  TaskAvailableFile,
  TaskUsage,
} from '@/api/types'
import { useAppStore } from '@/stores/app'
import { SUPPORTED_FILE_ACCEPT } from '@/utils/fileTypes'
import { errorMessage } from '@/utils/errors'

const props = defineProps<{
  taskId: string
  hasModel: boolean
  task: Task
  models: ModelInfo[]
  highlightMessageId?: string | null
}>()
const emit = defineEmits<{
  'usage-updated': [usage: TaskUsage | null]
  'task-updated': [task: Task]
  'open-artifacts': []
}>()

const app = useAppStore()
const router = useRouter()

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
const highlightedMessageId = ref<string | null>(null)
let controller: AbortController | null = null

const menuOpen = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const extraFiles = ref<TaskAvailableFile[]>([])
const librarySkills = ref<Skill[]>([])
const skillPickerOpen = ref(false)
const selectedSkill = ref<Skill | null>(null)
const selectedSkillId = computed(() => selectedSkill.value?.id ?? '')
const toolEvents = ref<
  { name: string; status: 'running' | 'ok' | 'error'; summary: string }[]
>([])
const runRefreshKey = ref(0)
const turnArtifacts = ref<Artifact[]>([])
const thinking = ref(false)
const elapsed = ref(0)
let thinkingTimer: ReturnType<typeof setInterval> | null = null

const TOOL_LABELS: Record<string, string> = {
  read_task_files: '读取可用文件',
  read_task_file: '读取文件内容',
  save_artifact: '保存成果',
  create_execution: '启动执行',
}

const SOURCE_LABELS: Record<string, string> = {
  project_inherited: '项目继承',
  task_added: '额外引用',
  temporary: '本轮临时',
  skill_asset: 'Skill 资料',
}

function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source
}

function messageTools(message: ChatMessage) {
  return message.metadata?.tools ?? []
}

function messageFiles(message: ChatMessage) {
  return message.metadata?.files ?? []
}

function chainDuration(message: ChatMessage): string {
  const ms = message.metadata?.duration_ms
  return ms && ms > 0 ? `${(ms / 1000).toFixed(1)}s` : ''
}

const selectedSkillLabel = computed(() => selectedSkill.value?.name ?? '')

const usageLabel = (usage: TaskUsage | null): string | null =>
  usage?.total_tokens ? `${usage.total_tokens} tokens` : null

function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  const el = listRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
  requestAnimationFrame(() => {
    el.scrollTop = el.scrollHeight
  })
  window.setTimeout(() => {
    el.scrollTop = el.scrollHeight
  }, 80)
}

async function scrollToMessage(messageId: string): Promise<void> {
  await nextTick()
  const el = listRef.value?.querySelector<HTMLElement>(
    '[data-message-id="' + messageId + '"]',
  )
  if (!el) {
    app.notify('info', '原消息不在当前对话窗口中')
    return
  }
  el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  highlightedMessageId.value = messageId
  window.setTimeout(() => {
    if (highlightedMessageId.value === messageId) highlightedMessageId.value = null
  }, 2600)
}

watch(
  () => props.highlightMessageId,
  (id) => {
    if (id) void scrollToMessage(id)
  },
)

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const data = await listTaskMessages(props.taskId)
    messages.value = data.messages
    taskUsage.value = data.task_usage
    if (props.highlightMessageId) void scrollToMessage(props.highlightMessageId)
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

function toggleMenu(): void {
  menuOpen.value = !menuOpen.value
}

function pickFile(): void {
  fileInput.value?.click()
}

async function onFileSelected(event: Event): Promise<void> {
  const inputEl = event.target as HTMLInputElement
  const file = inputEl.files?.[0]
  inputEl.value = ''
  if (!file) return
  uploading.value = true
  try {
    const uploaded = await uploadTaskTemporaryFile(props.taskId, file)
    extraFiles.value = [
      ...extraFiles.value,
      { file: uploaded, source: 'temporary' },
    ]
    app.notify('success', `已附加「${uploaded.filename}」（仅本轮）`)
  } catch (error) {
    app.notifyError(error)
  } finally {
    uploading.value = false
  }
}

async function removeExtra(item: TaskAvailableFile): Promise<void> {
  try {
    await removeTaskFileOverride(props.taskId, item.file.id)
    extraFiles.value = extraFiles.value.filter(
      (entry) => entry.file.id !== item.file.id,
    )
  } catch (error) {
    app.notifyError(error)
  }
}

async function openSkillPicker(): Promise<void> {
  try {
    librarySkills.value = await listSkills()
    skillPickerOpen.value = true
  } catch (error) {
    app.notifyError(error)
  }
}

function chooseSkill(skill: Skill): void {
  selectedSkill.value = skill
  skillPickerOpen.value = false
  menuOpen.value = false
}

function clearSelectedSkill(): void {
  selectedSkill.value = null
}

function goSkillLibrary(): void {
  menuOpen.value = false
  void router.push('/skills')
}

async function loadTurnArtifacts(ids: string[]): Promise<void> {
  try {
    const items = await Promise.all(ids.map((id) => getArtifact(id)))
    turnArtifacts.value = items
    app.notify('success', '本轮生成了 ' + items.length + ' 个成果')
  } catch {
    turnArtifacts.value = []
  }
}

function openArtifacts(): void {
  emit('open-artifacts')
}

async function send(): Promise<void> {
  const content = input.value.trim()
  if (!content || sending.value) return
  if (!props.hasModel) {
    streamError.value =
      '尚未配置可用模型：请先在 Settings 配置 DeepSeek API Key 或启用 Ollama。'
    return
  }

  input.value = ''
  resizeInput()
  sending.value = true
  streamError.value = null
  streamText.value = ''
  toolEvents.value = []
  turnArtifacts.value = []
  thinking.value = false
  elapsed.value = 0
  menuOpen.value = false
  if (thinkingTimer) clearInterval(thinkingTimer)
  thinkingTimer = setInterval(() => {
    elapsed.value += 1
  }, 1000)

  const attachmentIds = extraFiles.value.map((item) => item.file.id)
  const pendingMetadata = {
    skill: selectedSkill.value
      ? { id: selectedSkill.value.id, name: selectedSkill.value.name }
      : null,
    files: extraFiles.value.map((item) => ({
      filename: item.file.filename,
      source: 'temporary',
      status: 'included' as const,
    })),
  }
  extraFiles.value = []
  // 发送后清空输入栏的 Skill 选择（Task 引用仍保留，可在「+」中重新选择）
  selectedSkill.value = null
  messages.value = [
    ...messages.value,
    {
      id: `pending-${Date.now()}`,
      conversation_id: '',
      role: 'user',
      content,
      sequence: 0,
      usage: null,
      metadata: pendingMetadata,
      created_at: new Date().toISOString(),
    },
  ]
  await scrollToBottom()

  controller = new AbortController()
  let failed = false
  try {
    await streamTaskChat(
      props.taskId,
      {
        content,
        skill_id: selectedSkillId.value || undefined,
        file_ids: attachmentIds.length ? attachmentIds : undefined,
      },
      {
        onDelta: (text) => {
          thinking.value = false
          streamText.value += text
          void scrollToBottom()
        },
        onThinking: () => {
          thinking.value = true
          void scrollToBottom()
        },
        onToolCall: (call) => {
          toolEvents.value.push({
            name: call.name,
            status: 'running',
            summary: '',
          })
          void scrollToBottom()
        },
        onToolResult: (result) => {
          const item = [...toolEvents.value]
            .reverse()
            .find((entry) => entry.name === result.name && entry.status === 'running')
          if (item) {
            item.status = result.ok ? 'ok' : 'error'
            item.summary = result.summary
          }
        },
        onError: (error) => {
          failed = true
          streamError.value = error.message
        },
        onDone: (data) => {
          thinking.value = false
          taskUsage.value = data.task_usage as TaskUsage | null
          if (data.executions.length) {
            runRefreshKey.value += 1
            app.notify('info', '已启动执行')
          }
          if (data.artifacts.length) {
            void loadTurnArtifacts(data.artifacts)
          }
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
    thinking.value = false
    if (thinkingTimer) {
      clearInterval(thinkingTimer)
      thinkingTimer = null
    }
    streamText.value = ''
    controller = null
    await load()
    // 临时文件仅用于刚发送的这一轮，不再写入 Task 可用上下文。
    extraFiles.value = []
    if (failed) app.notify('error', '对话未完成，请查看错误信息')
  }
}

function stop(): void {
  controller?.abort()
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    void send()
  }
}

function onClickOutside(event: MouseEvent): void {
  const target = event.target as HTMLElement | null
  if (target?.closest('.composer')) return
  menuOpen.value = false
  skillPickerOpen.value = false
}

onMounted(() => {
  void load()
  document.addEventListener('click', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
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

    <RunProgress :task-id="taskId" :refresh-key="runRefreshKey" />

    <div v-if="!hasModel" class="notice notice--warning">
      <AppIcon name="alert" :size="15" />
      <span>尚未配置可用模型：请先在 Settings 中配置 DeepSeek API Key 或启用 Ollama。</span>
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
          直接提问，或让 AI 读取 Task 文件、生成成果、启动正式执行。上传文件与引用 Skill
          在输入框左下角的「+」里。
        </p>
      </div>

      <div v-else class="chat-messages">
        <article
          v-for="message in messages"
          :key="message.id"
          class="chat-message"
          :class="[
            `chat-message--${message.role}`,
            { 'chat-message--highlight': highlightedMessageId === message.id },
          ]"
          :data-message-id="message.id"
        >
          <details
            v-if="message.role === 'assistant' && message.metadata"
            class="thought-chain"
          >
            <summary class="thought-chain__summary">
              <AppIcon name="sparkles" :size="11" />
              思路链
              <span v-if="messageTools(message).length">
                · {{ messageTools(message).length }} 步
              </span>
              <span v-if="chainDuration(message)"> · {{ chainDuration(message) }}</span>
            </summary>
            <ol v-if="messageTools(message).length" class="thought-chain__list">
              <li
                v-for="(tool, index) in messageTools(message)"
                :key="index"
                class="thought-chain__item"
              >
                <span
                  class="thought-chain__dot"
                  :class="tool.ok ? 'thought-chain__dot--ok' : 'thought-chain__dot--fail'"
                />
                <span>{{ toolLabel(tool.name) }}</span>
                <span v-if="tool.summary" class="thought-chain__detail">{{ tool.summary }}</span>
              </li>
            </ol>
            <p v-else class="thought-chain__direct">直接回答，未调用工具。</p>
          </details>

          <header class="chat-message__head">
            <span class="chat-message__role">{{ message.role === 'user' ? 'You' : 'Assistant' }}</span>
            <span v-if="usageLabel(message.usage)" class="chat-message__usage">
              {{ usageLabel(message.usage) }}
            </span>
          </header>
          <div
            v-if="
              message.role === 'user' &&
              (message.metadata?.skill || messageFiles(message).length)
            "
            class="message-attachments"
          >
            <span v-if="message.metadata?.skill" class="chip chip--skill">
              <AppIcon name="sparkles" :size="11" />
              {{ message.metadata.skill.name }}
            </span>
            <span
              v-for="file in messageFiles(message)"
              :key="file.filename"
              class="chip chip--file"
              :title="`${sourceLabel(file.source)}${file.status === 'skipped' ? '（超预算未展开）' : file.status === 'failed' ? '（读取失败）' : ''}`"
            >
              <AppIcon name="file" :size="11" />
              {{ file.filename }}
              <span class="chip__hint">{{ sourceLabel(file.source) }}</span>
            </span>
          </div>

          <div class="chat-message__body">
            <MarkdownText v-if="message.role === 'assistant'" :text="message.content" />
            <p v-else class="chat-message__text">{{ message.content }}</p>
          </div>
        </article>

        <article v-if="sending" class="chat-message chat-message--assistant">
          <header class="chat-message__head">
            <span class="chat-message__role">Assistant</span>
            <span class="chat-message__usage">{{ elapsed }}s</span>
            <span class="spinner spinner--sm" aria-hidden="true" />
          </header>
          <details v-if="toolEvents.length || thinking" class="work-log" open>
            <summary class="work-log__summary">
              工作详情
              <span class="work-log__thinking">
                {{ thinking ? '模型思考中…' : '生成中…' }} {{ elapsed }}s
              </span>
            </summary>
            <ul v-if="toolEvents.length" class="tool-events">
              <li v-for="(event, index) in toolEvents" :key="index" class="tool-event">
                <span class="tool-event__dot" :class="`tool-event__dot--${event.status}`" />
                <span>{{ toolLabel(event.name) }}</span>
                <span v-if="event.summary" class="tool-event__summary">{{ event.summary }}</span>
              </li>
            </ul>
          </details>
          <div class="chat-message__body">
            <MarkdownText v-if="streamText" :text="streamText" />
            <p v-else class="chat-message__placeholder">
              {{ toolEvents.length ? '正在调用工具…' : '正在生成…' }}
            </p>
          </div>
        </article>
      </div>
    </div>

    <div v-if="turnArtifacts.length" class="artifact-receipt" role="status">
      <span class="artifact-receipt__icon"><AppIcon name="file" :size="18" /></span>
      <div class="artifact-receipt__body">
        <p class="artifact-receipt__title">本轮生成了 {{ turnArtifacts.length }} 个成果</p>
        <p class="artifact-receipt__meta">
          {{ turnArtifacts.map((item) => item.title).join(' · ') }}
        </p>
      </div>
      <button type="button" class="btn btn--primary btn--sm" @click="openArtifacts">
        查看成果
      </button>
    </div>

    <div v-if="streamError" class="panel panel--error chat-error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">本次对话失败</p>
        <p class="panel--error__desc">{{ streamError }}</p>
      </div>
    </div>

    <div class="composer">
      <div v-if="extraFiles.length || selectedSkill" class="composer__chips">
        <span v-for="item in extraFiles" :key="item.file.id" class="chip chip--file">
          <AppIcon name="file" :size="11" />
          {{ item.file.filename }}
          <button
            type="button"
            class="chip__close"
            title="移除临时引用"
            @click="removeExtra(item)"
          >
            <AppIcon name="close" :size="10" />
          </button>
        </span>
        <span v-if="selectedSkill" class="chip chip--skill">
          <AppIcon name="sparkles" :size="11" />
          {{ selectedSkillLabel }}
          <button
            type="button"
            class="chip__close"
            title="取消选择"
            @click="clearSelectedSkill()"
          >
            <AppIcon name="close" :size="10" />
          </button>
        </span>
      </div>

      <div class="composer__box">
        <textarea
          ref="inputRef"
          v-model="input"
          class="composer__input"
          rows="2"
          :placeholder="hasModel ? '输入消息…（Enter 发送，Shift+Enter 换行）' : '请先配置模型'"
          :disabled="sending"
          aria-label="对话输入框"
          @input="resizeInput"
          @keydown="onKeydown"
        />
        <div class="composer__bar">
          <div class="composer__left">
            <button
              type="button"
              class="composer__plus"
              title="添加文件 / 引用 Skill"
              :disabled="sending"
              @click.stop="toggleMenu"
            >
              <AppIcon name="plus" :size="15" />
            </button>
            <div v-if="menuOpen" class="composer__menu" @click.stop>
              <button type="button" class="composer__menu-item" @click="pickFile">
                <AppIcon name="upload" :size="14" />
                上传文件（临时引用）
              </button>
              <button type="button" class="composer__menu-item" @click="openSkillPicker">
                <AppIcon name="sparkles" :size="14" />
                引用 Skill
              </button>
              <button type="button" class="composer__menu-item" @click="goSkillLibrary">
                <AppIcon name="library" :size="14" />
                管理 Skill Library
              </button>
            </div>
            <input
              ref="fileInput"
              class="hidden-input"
              type="file"
              :accept="SUPPORTED_FILE_ACCEPT"
              @change="onFileSelected"
            />
            <span v-if="uploading" class="composer__hint">上传中…</span>
            <ModelControls
              :task="task"
              :models="models"
              @task-updated="emit('task-updated', $event)"
              @notify="app.notify('error', $event)"
            />
          </div>
          <div class="composer__right">
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

      <div v-if="skillPickerOpen" class="skill-picker" @click.stop>
        <header class="skill-picker__head">
          <span>引用 Skill</span>
          <button type="button" class="btn btn--ghost btn--sm" @click="skillPickerOpen = false">
            关闭
          </button>
        </header>
        <p class="skill-picker__label">从 Skill Library 选择（仅对下一条消息生效）</p>
        <ul class="skill-picker__list">
          <li v-for="skill in librarySkills" :key="skill.id" class="skill-picker__row">
            <button
              type="button"
              class="skill-picker__pick"
              :class="{ 'skill-picker__pick--active': selectedSkillId === skill.id }"
              @click="chooseSkill(skill)"
            >
              <span class="skill-picker__name">{{ skill.name }}</span>
              <span class="skill-picker__desc">{{ skill.description }}</span>
            </button>
            <span v-if="selectedSkillId === skill.id" class="chip chip--muted">已选</span>
          </li>
        </ul>
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
  align-items: flex-start;
  gap: 8px;
  margin: 24px 18px;
  padding: 24px 0 24px 20px;
  border-left: 2px solid var(--accent);
  color: var(--text-muted);
  text-align: left;
}

.chat-empty__title {
  margin: 0;
  color: var(--text);
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.02em;
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
  gap: 0;
  padding: 4px 18px;
}

.chat-message {
  width: 100%;
  max-width: 100%;
  padding: 16px 0;
  border: 0;
  border-bottom: 1px solid var(--border);
  border-radius: 0;
  background: transparent;
}

.chat-message--user {
  align-self: stretch;
  padding-left: 16px;
  border-left: 2px solid var(--accent);
  background: transparent;
}

.chat-message--assistant {
  align-self: stretch;
}

.chat-message--highlight {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  box-shadow: inset 2px 0 0 var(--accent);
  animation: message-highlight 2.4s ease-out;
}

@keyframes message-highlight {
  0% {
    background: color-mix(in srgb, var(--accent) 24%, transparent);
  }
  100% {
    background: color-mix(in srgb, var(--accent) 12%, transparent);
  }
}

.chat-message__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.chat-message__role {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.chat-message__usage {
  margin-left: auto;
  padding: 0;
  border: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--text-faint);
}

.chat-message__body {
  min-width: 0;
}

.chat-message__text {
  margin: 0;
  font-size: 14.5px;
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

.thought-chain {
  margin: 0 0 8px;
  padding: 6px 8px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--bg) 55%, transparent);
}

.thought-chain__summary {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-faint);
  user-select: none;
}

.thought-chain__list {
  margin: 8px 0 0;
  padding: 0 0 0 4px;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.thought-chain__item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.thought-chain__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-faint);
}

.thought-chain__dot--ok {
  background: var(--success);
}

.thought-chain__dot--fail {
  background: var(--danger);
}

.thought-chain__detail {
  color: var(--text-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thought-chain__direct {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-faint);
}

.message-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 8px;
}

.chip__hint {
  color: var(--text-faint);
  font-size: 12px;
}

.work-log {
  margin: 0 0 8px;
  padding: 6px 8px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--bg) 60%, transparent);
}

.work-log--after {
  margin: 0;
}

.work-log__summary {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-faint);
  user-select: none;
}

.work-log__thinking {
  color: var(--accent);
}

.tool-events {
  list-style: none;
  margin: 0 0 8px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-event {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.tool-event__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-faint);
}

.tool-event__dot--running {
  background: var(--accent);
}

.tool-event__dot--ok {
  background: var(--success);
}

.tool-event__dot--error {
  background: var(--danger);
}

.tool-event__summary {
  color: var(--text-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-receipt {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 18px 14px;
  padding: 12px 14px;
  border: 1px solid var(--accent-border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--accent) 16%, var(--bg-raised));
  box-shadow: 0 8px 28px rgba(201, 122, 74, 0.14);
  animation: receipt-in 0.22s ease-out;
}

.artifact-receipt__icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--accent);
  color: #1b120d;
}

.artifact-receipt__body {
  min-width: 0;
  flex: 1;
}

.artifact-receipt__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.artifact-receipt__meta {
  margin: 2px 0 0;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes receipt-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-error {
  margin: 0;
}

.composer {
  position: relative;
}

.composer__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.chip--file,
.chip--skill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-subtle);
  font-size: 12px;
  color: var(--text-secondary);
}

.chip--skill {
  border-color: var(--accent-border);
  background: var(--accent-soft);
}

.chip__close {
  display: grid;
  place-items: center;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text-faint);
  cursor: pointer;
}

.chip__close:hover {
  color: var(--danger);
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
  gap: 10px;
  padding-top: 6px;
  border-top: 1px solid var(--border);
}

.composer__left {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.composer__right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.composer__plus {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  cursor: pointer;
}

.composer__plus:hover {
  border-color: var(--accent-border);
  color: var(--text);
}

.composer__menu {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 40;
  width: 220px;
  padding: 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated, var(--bg-subtle));
  box-shadow: var(--shadow-lg, 0 18px 40px rgba(0, 0, 0, 0.35));
}

.composer__menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 9px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.composer__menu-item:hover {
  background: var(--bg-hover);
  color: var(--text);
}

.composer__menu-item:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.composer__hint {
  font-size: 12px;
  color: var(--text-faint);
}

.hidden-input {
  display: none;
}

.skill-picker {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 41;
  width: 340px;
  max-height: 360px;
  overflow-y: auto;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated, var(--bg-subtle));
  box-shadow: var(--shadow-lg, 0 18px 40px rgba(0, 0, 0, 0.35));
}

.skill-picker__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
}

.skill-picker__label {
  margin: 10px 0 4px;
  font-size: 12px;
  color: var(--text-faint);
}

.skill-picker__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.skill-picker__row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.skill-picker__pick {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 7px 8px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
}

.skill-picker__pick:hover,
.skill-picker__pick--active {
  border-color: var(--accent-border);
  background: var(--accent-soft);
}

.skill-picker__name {
  font-size: 12px;
}

.skill-picker__desc {
  font-size: 12px;
  color: var(--text-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  font-size: 12px;
  color: var(--text-faint);
}

.notice--warning {
  border-color: var(--warning-soft);
  color: var(--warning);
}
</style>
