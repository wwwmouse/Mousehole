<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  listProviders,
  testProvider,
  updateProvider,
  updateWorkspace,
} from '@/api/endpoints'
import type { Provider, ProviderTestResult, ProviderUpdate } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/format'

const app = useAppStore()

const workspaceName = ref('')
const saving = ref(false)
const saveError = ref<string | null>(null)

const defaultTemperatureDraft = ref('')
const defaultMaxTokensDraft = ref('')
const contextBudgetDraft = ref('')
const savingDefaults = ref(false)

const providers = ref<Provider[]>([])
const loadingProviders = ref(true)
const providerError = ref<string | null>(null)
const keyDraft = ref<Record<string, string>>({})
const baseUrlDraft = ref<Record<string, string>>({})
const savingProvider = ref<string | null>(null)
const testingProvider = ref<string | null>(null)
const testResults = ref<Record<string, ProviderTestResult | null>>({})
const expanded = ref<Record<string, boolean>>({})

function toggleProvider(name: string): void {
  expanded.value[name] = !expanded.value[name]
}

const configuredCount = computed(
  () => providers.value.filter((item) => item.configured).length,
)

const workspace = computed(() => app.currentWorkspace)

const canSave = computed(() => {
  const name = workspaceName.value.trim()
  if (!workspace.value) return false
  return name.length > 0 && name !== workspace.value.name && !saving.value
})

watch(
  () => app.currentWorkspace?.id,
  () => {
    const current = app.currentWorkspace
    workspaceName.value = current?.name ?? ''
    defaultTemperatureDraft.value =
      current?.default_temperature != null ? String(current.default_temperature) : ''
    defaultMaxTokensDraft.value =
      current?.default_max_tokens != null ? String(current.default_max_tokens) : ''
    contextBudgetDraft.value =
      current?.context_budget_tokens != null ? String(current.context_budget_tokens) : ''
    saveError.value = null
  },
  { immediate: true },
)

async function saveWorkspace(): Promise<void> {
  const name = workspaceName.value.trim()
  if (!name) {
    saveError.value = '工作空间名称不能为空'
    return
  }
  saving.value = true
  saveError.value = null
  try {
    const updated = await app.renameWorkspace(name)
    app.notify('success', `工作空间名称已更新为「${updated.name}」`)
  } catch (error) {
    saveError.value = errorMessage(error)
    app.notifyError(error)
  } finally {
    saving.value = false
  }
}

async function reloadWorkspace(): Promise<void> {
  await app.loadWorkspace(true)
  workspaceName.value = app.currentWorkspace?.name ?? ''
}

async function saveDefaults(): Promise<void> {
  const current = app.currentWorkspace
  if (!current) return
  const temperature =
    defaultTemperatureDraft.value.trim() === ''
      ? null
      : Number(defaultTemperatureDraft.value)
  const maxTokens =
    defaultMaxTokensDraft.value.trim() === ''
      ? null
      : Number(defaultMaxTokensDraft.value)
  const contextBudget =
    contextBudgetDraft.value.trim() === ''
      ? null
      : Number(contextBudgetDraft.value)
  if (
    temperature !== null &&
    (Number.isNaN(temperature) || temperature < 0 || temperature > 2)
  ) {
    app.notify('error', 'Temperature 需在 0 到 2 之间')
    return
  }
  if (
    maxTokens !== null &&
    (!Number.isInteger(maxTokens) || maxTokens < 1 || maxTokens > 32000)
  ) {
    app.notify('error', 'Max tokens 需为 1 到 32000 的整数')
    return
  }
  if (
    contextBudget !== null &&
    (!Number.isInteger(contextBudget) || contextBudget < 2000 || contextBudget > 1000000)
  ) {
    app.notify('error', '上下文预算需为 2000 到 1000000 的整数')
    return
  }
  savingDefaults.value = true
  try {
    await updateWorkspace(current.id, {
      default_temperature: temperature,
      default_max_tokens: maxTokens,
      context_budget_tokens: contextBudget,
    })
    await app.loadWorkspace(true)
    app.notify('success', '模型默认参数已保存')
  } catch (error) {
    app.notifyError(error)
  } finally {
    savingDefaults.value = false
  }
}

async function loadProviders(): Promise<void> {
  loadingProviders.value = true
  providerError.value = null
  try {
    providers.value = await listProviders()
    for (const provider of providers.value) {
      baseUrlDraft.value[provider.name] = provider.base_url
      if (!(provider.name in keyDraft.value)) keyDraft.value[provider.name] = ''
    }
  } catch (error) {
    providerError.value = errorMessage(error)
  } finally {
    loadingProviders.value = false
  }
}

async function saveProvider(name: string): Promise<void> {
  const provider = providers.value.find((item) => item.name === name)
  if (!provider) return
  const payload: ProviderUpdate = {}
  const key = (keyDraft.value[name] ?? '').trim()
  const baseUrl = (baseUrlDraft.value[name] ?? '').trim()
  if (key) payload.api_key = key
  if (baseUrl && baseUrl !== provider.base_url) payload.base_url = baseUrl
  if (!payload.api_key && !payload.base_url) {
    if (provider.configured) {
      app.notify('info', '没有需要保存的修改')
      return
    }
    payload.base_url = baseUrl || provider.base_url
  }
  savingProvider.value = name
  try {
    const updated = await updateProvider(name, payload)
    keyDraft.value[name] = ''
    if (updated.kind === 'openai' && !updated.configured) {
      app.notify('info', `${name} 配置已保存，但尚未填写 API Key`)
    } else {
      app.notify('success', `${name} 配置已保存`)
    }
    await loadProviders()
  } catch (error) {
    app.notifyError(error)
  } finally {
    savingProvider.value = null
  }
}

async function runTest(name: string): Promise<void> {
  testingProvider.value = name
  testResults.value[name] = null
  try {
    testResults.value[name] = await testProvider(name)
  } catch (error) {
    testResults.value[name] = { ok: false, message: errorMessage(error) }
  } finally {
    testingProvider.value = null
  }
}

onMounted(() => {
  void reloadWorkspace()
  void loadProviders()
})
</script>

<template>
  <div class="settings-page">
    <PageHeader
      title="Settings"
      description="应用级设置与当前工作空间信息。"
    />

    <LoadingState v-if="app.workspaceState === 'loading'" label="正在加载工作空间…" />

    <div v-else-if="app.workspaceState === 'error'" class="panel panel--error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">工作空间加载失败</p>
        <p class="panel--error__desc">{{ app.workspaceError }}</p>
      </div>
      <button type="button" class="btn btn--ghost btn--sm" @click="reloadWorkspace">重试</button>
    </div>

    <EmptyState
      v-else-if="!workspace"
      icon="database"
      title="没有可用的工作空间"
      description="后端尚未返回任何 Workspace。请确认后端服务与数据库迁移已就绪。"
    >
      <button type="button" class="btn btn--ghost" @click="reloadWorkspace">重新加载</button>
    </EmptyState>

    <template v-else>
      <section class="card settings-card">
        <header class="settings-card__head">
          <div>
            <h2 class="settings-card__title">Workspace</h2>
            <p class="settings-card__desc">当前工作空间的基础信息与显示名称。</p>
          </div>
          <span class="chip chip--muted">Global Workspace</span>
        </header>
        <div class="settings-card__body">
          <label class="field">
            <span class="field__label">工作空间名称</span>
            <div class="inline-field">
              <input
                v-model="workspaceName"
                class="input"
                type="text"
                maxlength="200"
                placeholder="工作空间名称"
                :disabled="saving"
                @keyup.enter="canSave && saveWorkspace()"
              />
              <button
                type="button"
                class="btn btn--primary"
                :disabled="!canSave"
                @click="saveWorkspace"
              >
                <span v-if="saving" class="spinner spinner--sm" aria-hidden="true" />
                {{ saving ? '保存中…' : '保存' }}
              </button>
            </div>
            <span class="field__hint">名称会显示在首页问候与侧边栏工作空间区域。</span>
            <span v-if="saveError" class="field__error">{{ saveError }}</span>
          </label>

          <dl class="kv">
            <div class="kv__row">
              <dt>Workspace ID</dt>
              <dd class="kv__mono">{{ workspace.id }}</dd>
            </div>
            <div class="kv__row">
              <dt>创建时间</dt>
              <dd>{{ formatDateTime(workspace.created_at) }}</dd>
            </div>
            <div class="kv__row">
              <dt>更新时间</dt>
              <dd>{{ formatDateTime(workspace.updated_at) }}</dd>
            </div>
            <div class="kv__row">
              <dt>描述</dt>
              <dd>{{ workspace.description || '—' }}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section class="card settings-card">
        <header class="settings-card__head">
          <div>
            <h2 class="settings-card__title">模型 Provider</h2>
            <p class="settings-card__desc">
              配置云端模型密钥或本地 Ollama；密钥只保存在本机，接口只返回掩码。
            </p>
          </div>
          <span class="chip chip--muted">{{ configuredCount }} / {{ providers.length }} 已配置</span>
        </header>
        <div class="settings-card__body">
          <LoadingState v-if="loadingProviders" compact label="正在加载 Provider…" />

          <div v-else-if="providerError" class="panel panel--error">
            <AppIcon name="alert" :size="16" />
            <div>
              <p class="panel--error__title">Provider 加载失败</p>
              <p class="panel--error__desc">{{ providerError }}</p>
            </div>
            <button type="button" class="btn btn--ghost btn--sm" @click="loadProviders">重试</button>
          </div>

          <div v-else class="provider-list">
            <article
              v-for="provider in providers"
              :key="provider.name"
              class="provider-card"
              :class="{
                'provider-card--configured': provider.configured,
                'provider-card--open': expanded[provider.name],
              }"
            >
              <header
                class="provider-card__head"
                role="button"
                tabindex="0"
                :aria-expanded="Boolean(expanded[provider.name])"
                @click="toggleProvider(provider.name)"
                @keydown.enter.prevent="toggleProvider(provider.name)"
                @keydown.space.prevent="toggleProvider(provider.name)"
              >
                <div class="provider-card__title">
                  <AppIcon
                    :name="expanded[provider.name] ? 'chevron-down' : 'chevron-right'"
                    :size="14"
                  />
                  <strong>{{ provider.name }}</strong>
                  <span class="chip chip--muted">{{ provider.kind }}</span>
                </div>
                <span
                  class="chip provider-card__status"
                  :class="provider.configured ? 'provider-card__status--ok' : 'chip--muted'"
                >
                  {{ provider.configured ? '已配置' : '未配置' }}
                </span>
              </header>

              <div v-if="expanded[provider.name]" class="provider-card__body">
                <label v-if="provider.kind === 'openai'" class="field">
                  <span class="field__label">API Key</span>
                  <input
                    v-model="keyDraft[provider.name]"
                    class="input"
                    type="password"
                    autocomplete="off"
                    :placeholder="provider.masked_key || '尚未配置'"
                  />
                  <span class="field__hint">保存后只返回掩码；不会写入日志。</span>
                </label>

                <label class="field">
                  <span class="field__label">Base URL</span>
                  <input v-model="baseUrlDraft[provider.name]" class="input" type="text" />
                  <span class="field__hint">
                    Ollama 保存后即视为启用；请确认本机 Ollama 正在运行。
                  </span>
                </label>

                <div v-if="provider.models.length" class="provider-card__models">
                  <span class="field__label">可用模型</span>
                  <div class="chip-row">
                    <span v-for="model in provider.models" :key="model" class="chip chip--muted">
                      {{ model }}
                    </span>
                  </div>
                </div>

                <div class="provider-card__actions">
                  <button
                    type="button"
                    class="btn btn--primary btn--sm"
                    :disabled="savingProvider === provider.name"
                    @click="saveProvider(provider.name)"
                  >
                    <span
                      v-if="savingProvider === provider.name"
                      class="spinner spinner--sm"
                      aria-hidden="true"
                    />
                    保存
                  </button>
                  <button
                    type="button"
                    class="btn btn--ghost btn--sm"
                    :disabled="testingProvider === provider.name"
                    @click="runTest(provider.name)"
                  >
                    测试连接
                  </button>
                  <span
                    v-if="testResults[provider.name]"
                    class="provider-test"
                    :class="testResults[provider.name]?.ok ? 'provider-test--ok' : 'provider-test--fail'"
                  >
                    {{ testResults[provider.name]?.message }}
                  </span>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 860px;
}

.settings-card {
  padding: 0;
  overflow: hidden;
}

.settings-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
}

.settings-card__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.settings-card__desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.settings-card__body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 18px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.field__hint {
  font-size: 11.5px;
  color: var(--text-faint);
  line-height: 1.5;
}

.field__error {
  font-size: 11.5px;
  color: var(--danger);
}

.inline-field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.default-params {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.default-params .field {
  min-width: 160px;
}

.inline-field .input {
  flex: 1;
}

.kv {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  overflow: hidden;
}

.kv__row {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  gap: 12px;
  padding: 9px 13px;
  border-bottom: 1px solid var(--border);
  font-size: 12.5px;
}

.kv__row:last-child {
  border-bottom: none;
}

.kv dt {
  color: var(--text-faint);
}

.kv dd {
  margin: 0;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.kv__mono {
  font-family: var(--font-mono);
  font-size: 11.5px;
}

.disabled-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  opacity: 0.55;
}

.settings-card__note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  padding: 11px 13px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-sm);
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--text-muted);
}

.settings-card__note :deep(svg) {
  flex-shrink: 0;
  margin-top: 1px;
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.provider-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
}

.provider-card--configured {
  border-color: var(--accent-border);
}

.provider-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.provider-card__head:hover .provider-card__title strong {
  color: var(--text);
}

.provider-card__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 2px;
  border-top: 1px solid var(--border);
}

.provider-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.provider-card__status--ok {
  color: var(--success);
  border-color: var(--success-soft);
}

.provider-card__models {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.provider-card__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 2px;
  border-top: 1px solid var(--border);
}

.provider-test {
  font-size: 11.5px;
}

.provider-test--ok {
  color: var(--success);
}

.provider-test--fail {
  color: var(--danger);
}

@media (max-width: 720px) {
  .disabled-form {
    grid-template-columns: minmax(0, 1fr);
  }

  .kv__row {
    grid-template-columns: minmax(0, 1fr);
    gap: 3px;
  }
}
</style>
