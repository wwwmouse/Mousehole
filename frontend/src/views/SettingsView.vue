<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingState from '@/components/LoadingState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/format'

const app = useAppStore()

const workspaceName = ref('')
const saving = ref(false)
const saveError = ref<string | null>(null)

const workspace = computed(() => app.currentWorkspace)

const canSave = computed(() => {
  const name = workspaceName.value.trim()
  if (!workspace.value) return false
  return name.length > 0 && name !== workspace.value.name && !saving.value
})

watch(
  () => app.currentWorkspace?.id,
  () => {
    workspaceName.value = app.currentWorkspace?.name ?? ''
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

onMounted(() => {
  void reloadWorkspace()
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
            <h2 class="settings-card__title">Application Settings</h2>
            <p class="settings-card__desc">模型 Provider 与密钥配置将在 Phase 2 提供。</p>
          </div>
          <span class="chip chip--muted">Phase 2</span>
        </header>
        <div class="settings-card__body">
          <div class="disabled-form">
            <label class="field">
              <span class="field__label">模型 Provider</span>
              <select class="select" disabled>
                <option>将在 Phase 2 提供</option>
              </select>
            </label>
            <label class="field">
              <span class="field__label">API Key</span>
              <input class="input" type="password" value="" placeholder="不在此阶段存储密钥" disabled />
            </label>
          </div>
          <p class="settings-card__note">
            <AppIcon name="info" :size="14" />
            <span>
              Phase 1 不接入模型供应商，因此此处没有可配置项。前端不会伪造已保存的 Provider 或密钥状态。
            </span>
          </p>
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
