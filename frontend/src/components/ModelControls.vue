<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import ParticleSlider from '@/components/ParticleSlider.vue'
import { updateTask, updateWorkspace } from '@/api/endpoints'
import type { ModelInfo, Task } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'

const props = defineProps<{ task: Task; models: ModelInfo[] }>()
const emit = defineEmits<{ 'task-updated': [task: Task]; notify: [message: string] }>()

const app = useAppStore()

const open = ref(false)
const saving = ref(false)
const modelValue = ref('')
const temperature = ref(0.7)
const maxTokens = ref(4096)
const contextBudget = ref(32768)

const DEFAULT_TEMPERATURE = 0.7
const DEFAULT_MAX_TOKENS = 4096
const DEFAULT_CONTEXT_BUDGET = 32768

const workspace = computed(() => app.currentWorkspace)

const modelLabel = computed(() => {
  if (!modelValue.value) return '未选择模型'
  const [, model] = modelValue.value.split('::')
  return model || '未选择模型'
})

const effectiveProvider = computed(() => {
  const [provider] = modelValue.value.split('::')
  return provider || ''
})

let saveTimer: ReturnType<typeof setTimeout> | null = null

function syncFromTask(): void {
  const current = props.task
  modelValue.value = current.model_provider
    ? `${current.model_provider}::${current.model_name ?? ''}`
    : ''
  temperature.value =
    current.temperature ??
    app.currentWorkspace?.default_temperature ??
    DEFAULT_TEMPERATURE
  maxTokens.value =
    current.max_tokens ??
    app.currentWorkspace?.default_max_tokens ??
    DEFAULT_MAX_TOKENS
  contextBudget.value =
    app.currentWorkspace?.context_budget_tokens ?? DEFAULT_CONTEXT_BUDGET
}

watch(() => props.task.id, syncFromTask, { immediate: true })
watch(
  () => [
    props.task.temperature,
    props.task.max_tokens,
    props.task.model_provider,
    props.task.model_name,
  ],
  syncFromTask,
)
watch(
  () => app.currentWorkspace?.context_budget_tokens,
  (value) => {
    if (value != null) contextBudget.value = value
  },
)

function scheduleSave(): void {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    void save()
  }, 550)
}

async function save(): Promise<void> {
  const current = props.task
  saving.value = true
  try {
    const [provider, model] = modelValue.value.split('::')
    const updated = await updateTask(current.id, {
      model_provider: provider || null,
      model_name: model || null,
      temperature: temperature.value,
      max_tokens: maxTokens.value,
    })
    emit('task-updated', updated)
    if (workspace.value && contextBudget.value !== workspace.value.context_budget_tokens) {
      await updateWorkspace(workspace.value.id, {
        context_budget_tokens: contextBudget.value,
      })
      await app.loadWorkspace(true)
    }
  } catch (error) {
    emit('notify', errorMessage(error))
  } finally {
    saving.value = false
  }
}

function onModelChange(): void {
  void save()
}

function onClickOutside(event: MouseEvent): void {
  const target = event.target as HTMLElement | null
  if (target?.closest('.model-controls')) return
  open.value = false
}

watch(open, (value) => {
  if (value) document.addEventListener('click', onClickOutside)
  else document.removeEventListener('click', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
  if (saveTimer) clearTimeout(saveTimer)
})
</script>

<template>
  <div class="model-controls">
    <button
      type="button"
      class="model-controls__trigger"
      :title="modelValue ? `当前模型：${modelValue.replace('::', ' / ')}` : '选择模型'"
      @click.stop="open = !open"
    >
      <AppIcon name="sparkles" :size="13" />
      <span class="model-controls__name">{{ modelLabel }}</span>
      <AppIcon name="chevron-down" :size="12" />
    </button>

    <div v-if="open" class="model-controls__panel" @click.stop>
      <header class="model-controls__head">
        <span>模型与参数</span>
        <span v-if="saving" class="spinner spinner--sm" aria-hidden="true" />
      </header>

      <label class="field">
        <span class="field__label">模型</span>
        <select v-model="modelValue" class="select" @change="onModelChange">
          <option value="">未选择</option>
          <option
            v-for="item in models"
            :key="`${item.provider}::${item.model}`"
            :value="`${item.provider}::${item.model}`"
          >
            {{ item.provider }} / {{ item.model }}
          </option>
        </select>
      </label>

      <ParticleSlider
        v-model="temperature"
        label="Temperature"
        :min="0"
        :max="2"
        :step="0.1"
        :format="(value: number) => value.toFixed(1)"
        min-label="精确 0.0"
        max-label="发散 2.0"
        @update:model-value="scheduleSave"
      />
      <ParticleSlider
        v-model="maxTokens"
        label="Max tokens"
        :min="512"
        :max="8192"
        :step="256"
        unit=""
        min-label="512"
        max-label="8192"
        @update:model-value="scheduleSave"
      />
      <ParticleSlider
        v-model="contextBudget"
        label="上下文预算"
        :min="4000"
        :max="200000"
        :step="1000"
        min-label="4k"
        max-label="200k"
        @update:model-value="scheduleSave"
      />

    </div>
  </div>
</template>

<style scoped>
.model-controls {
  position: relative;
}

.model-controls__trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-size: 11.5px;
  cursor: pointer;
}

.model-controls__trigger:hover {
  border-color: var(--accent-border);
  color: var(--text);
}

.model-controls__name {
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-controls__panel {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 40;
  width: 300px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated, var(--bg-subtle));
  box-shadow: var(--shadow-lg, 0 18px 40px rgba(0, 0, 0, 0.35));
}

.model-controls__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
}

.model-controls__hint {
  margin: 0;
  font-size: 10.5px;
  line-height: 1.5;
  color: var(--text-faint);
}
</style>
