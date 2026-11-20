<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import LoadingState from '@/components/LoadingState.vue'
import MarkdownText from '@/components/MarkdownText.vue'
import ModelControls from '@/components/ModelControls.vue'
import RunProgress from '@/components/RunProgress.vue'
import { streamTaskChat } from '@/api/chat'
import {
  addTaskSkill,
  createExecution,
  getTaskFiles,
  listSkills,
  listTaskMessages,
  listTaskSkills,
  removeTaskFileOverride,
  removeTaskSkill,
  updateTaskFile,
  uploadFile,
} from '@/api/endpoints'
import type {
  ChatMessage,
  ModelInfo,
  Skill,
  Task,
  TaskAvailableFile,
  TaskUsage,
} from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'

const props = defineProps<{
  taskId: string
  hasModel: boolean
  task: Task
  models: ModelInfo[]
}>()
const emit = defineEmits<{
  'usage-updated': [usage: TaskUsage | null]
  'open-artifacts': []
  'task-updated': [task: Task]
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
let controller: AbortController | null = null

const menuOpen = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const extraFiles = ref<TaskAvailableFile[]>([])
const taskSkills = ref<Skill[]>([])
const librarySkills = ref<Skill[]>([])
const skillPickerOpen = ref(false)
const selectedSkillId = ref('')
const toolEvents = ref<
  { name: string; status: 'running' | 'ok' | 'error'; summary: string }[]
>([])
const toolOutputs = ref<{ artifacts: string[]; executions: string[] } | null>(null)
const runRefreshKey = ref(0)
const thinking = ref(false)
const thinkingElapsed = ref(0)
let thinkingTimer: ReturnType<typeof setInterval> | null = null

const TOOL_LABELS: Record<string, string> = {
  read_task_files: '读取可用文件',
  read_task_file: '读取文件内容',
  save_artifact: '保存成果',
  create_execution: '启动执行',
}

const selectedSkill = computed(
  () => taskSkills.value.find((item) => item.id === selectedSkillId.value) ?? null,
)

const usageLabel = (usage: TaskUsage | null): string | null =>
  usage?.total_tokens ? `${usage.total_tokens} tokens` : null

function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name
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

async function loadComposer(): Promise<void> {
  try {
    const [context, skills] = await Promise.all([
      getTaskFiles(props.taskId),
      listTaskSkills(props.taskId),
    ])
    extraFiles.value = context.available.filter(
      (item) => item.source === 'task_added',
    )
    taskSkills.value = skills
    if (
      selectedSkillId.value &&
      !skills.some((item) => item.id === selectedSkillId.value)
    ) {
      selectedSkillId.value = ''
    }
  } catch (error) {
    streamError.value = errorMessage(error)
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
  if (menuOpen.value) void loadComposer()
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
    const uploaded = await uploadFile(file)
    await updateTaskFile(props.taskId, {
      file_id: uploaded.id,
      action: 'include',
    })
    app.notify('success', `已临时引用「${uploaded.filename}」`)
    await loadComposer()
  } catch (error) {
    app.notifyError(error)
  } finally {
    uploading.value = false
  }
}

async function removeExtra(item: TaskAvailableFile): Promise<void> {
  try {
    await removeTaskFileOverride(props.taskId, item.file.id)
    await loadComposer()
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

async function chooseSkill(skill: Skill): Promise<void> {
  try {
    if (!taskSkills.value.some((item) => item.id === skill.id)) {
      await addTaskSkill(props.taskId, skill.id)
      await loadComposer()
      app.notify('success', `已引入 Skill「${skill.name}」`)
    }
    selectedSkillId.value = skill.id
    skillPickerOpen.value = false
    menuOpen.value = false
  } catch (error) {
    app.notifyError(error)
  }
}

async function dropTaskSkill(skill: Skill): Promise<void> {
  try {
    await removeTaskSkill(props.taskId, skill.id)
    if (selectedSkillId.value === skill.id) selectedSkillId.value = ''
    await loadComposer()
  } catch (error) {
    app.notifyError(error)
  }
}

async function runExecution(): Promise<void> {
  if (!props.hasModel) {
    app.notify('error', '尚未配置可用模型')
    return
  }
  try {
    await createExecution(props.taskId, selectedSkillId.value || undefined)
    menuOpen.value = false
    runRefreshKey.value += 1
    app.notify('info', '已启动执行，可在对话上方查看工作进度')
  } catch (error) {
    app.notifyError(error)
  }
}

function goSkillLibrary(): void {
  menuOpen.value = false
  void router.push('/skills')
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
  toolOutputs.value = null
  thinking.value = false
  thinkingElapsed.value = 0
  menuOpen.value = false
  if (thinkingTimer) clearInterval(thinkingTimer)
  thinkingTimer = setInterval(() => {
    if (thinking.value) thinkingElapsed.value += 1
  }, 1000)

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
          if (data.executions.length) runRefreshKey.value += 1
          if (data.artifacts.length || data.executions.length) {
            toolOutputs.value = {
              artifacts: data.artifacts,
              executions: data.executions,
            }
            app.notify(
              'success',
              data.artifacts.length ? '已生成成果，可在 Artifacts 查看' : '已启动执行',
            )
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
    await loadComposer()
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

function onClickOutside(event: MouseEvent): void {
  const target = event.target as HTMLElement | null
  if (target?.closest('.composer')) return
  menuOpen.value = false
  skillPickerOpen.value = false
}

onMounted(() => {
  void load()
  void loadComposer()
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
          <details v-if="toolEvents.length || thinking" class="work-log" open>
            <summary class="work-log__summary">
              工作详情
              <span v-if="thinking" class="work-log__thinking">
                模型思考中… {{ thinkingElapsed }}s
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

    <div v-if="streamError" class="panel panel--error chat-error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">本次对话失败</p>
        <p class="panel--error__desc">{{ streamError }}</p>
      </div>
    </div>

    <details v-if="toolEvents.length && !sending" class="work-log work-log--after" open>
      <summary class="work-log__summary">上次工作详情</summary>
      <ul class="tool-events">
        <li v-for="(event, index) in toolEvents" :key="index" class="tool-event">
          <span class="tool-event__dot" :class="`tool-event__dot--${event.status}`" />
          <span>{{ toolLabel(event.name) }}</span>
          <span v-if="event.summary" class="tool-event__summary">{{ event.summary }}</span>
        </li>
      </ul>
    </details>

    <div v-if="toolOutputs" class="tool-output">
      <AppIcon name="file" :size="14" />
      <span>
        {{ toolOutputs.artifacts.length ? '已生成成果' : '已启动执行' }}
      </span>
      <button type="button" class="btn btn--ghost btn--sm" @click="emit('open-artifacts')">
        查看 Artifacts
      </button>
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
          {{ selectedSkill.name }}
          <button type="button" class="chip__close" title="取消选择" @click="selectedSkillId = ''">
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
          :placeholder="hasModel ? '输入消息…（Ctrl+Enter 发送）' : '请先配置模型'"
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
              title="添加文件 / 引用 Skill / 执行"
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
              <button
                type="button"
                class="composer__menu-item"
                :disabled="!hasModel"
                @click="runExecution"
              >
                <AppIcon name="send" :size="14" />
                执行当前 Skill
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
              accept=".pdf,.md,.markdown,.txt"
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
        <p v-if="taskSkills.length" class="skill-picker__label">Task 已引用</p>
        <ul v-if="taskSkills.length" class="skill-picker__list">
          <li v-for="skill in taskSkills" :key="skill.id" class="skill-picker__row">
            <button type="button" class="skill-picker__pick" @click="chooseSkill(skill)">
              <span class="skill-picker__name">{{ skill.name }}</span>
              <span class="skill-picker__desc">{{ skill.description }}</span>
            </button>
            <button type="button" class="btn btn--ghost btn--sm" @click="dropTaskSkill(skill)">
              移除
            </button>
          </li>
        </ul>
        <p class="skill-picker__label">Skill Library</p>
        <ul class="skill-picker__list">
          <li
            v-for="skill in librarySkills.filter(
              (item) => !taskSkills.some((ref) => ref.id === item.id),
            )"
            :key="skill.id"
            class="skill-picker__row"
          >
            <button type="button" class="skill-picker__pick" @click="chooseSkill(skill)">
              <span class="skill-picker__name">{{ skill.name }}</span>
              <span class="skill-picker__desc">{{ skill.description }}</span>
            </button>
            <button type="button" class="btn btn--ghost btn--sm" @click="chooseSkill(skill)">
              引入
            </button>
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
  font-size: 11px;
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
  font-size: 11.5px;
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

.chat-error {
  margin: 0;
}

.tool-output {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  font-size: 12px;
  color: var(--text-secondary);
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
  font-size: 11px;
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
  font-size: 11px;
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
  font-size: 10.5px;
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

.skill-picker__pick:hover {
  border-color: var(--border);
  background: var(--bg-hover);
}

.skill-picker__name {
  font-size: 12px;
}

.skill-picker__desc {
  font-size: 10.5px;
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
  font-size: 11px;
  color: var(--text-faint);
}

.notice--warning {
  border-color: var(--warning-soft);
  color: var(--warning);
}
</style>
