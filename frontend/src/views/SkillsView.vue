<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import FilePreviewModal from '@/components/FilePreviewModal.vue'
import LoadingState from '@/components/LoadingState.vue'
import Modal from '@/components/Modal.vue'
import {
  addSkillFile,
  createSkill,
  deleteSkill,
  listSkillFiles,
  listSkills,
  removeSkillFile,
  updateSkill,
  uploadFile,
} from '@/api/endpoints'
import type { Skill, SkillFileInfo } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/format'

const app = useAppStore()

const skills = ref<Skill[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const modalOpen = ref(false)
const editing = ref<Skill | null>(null)
const saving = ref(false)
const form = ref({ name: '', description: '', instruction: '', system_prompt: '' })
const formSnapshot = ref('')
const discardOpen = ref(false)
const formDirty = computed(
  () => JSON.stringify(form.value) !== formSnapshot.value,
)

const deleteTarget = ref<Skill | null>(null)
const deleting = ref(false)
const previewFileId = ref<string | null>(null)

const attachments = ref<SkillFileInfo[]>([])
const assetUploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)

async function loadAttachments(skillId: string): Promise<void> {
  try {
    attachments.value = await listSkillFiles(skillId)
  } catch {
    attachments.value = []
  }
}

async function onAssetSelected(event: Event, withPath: boolean): Promise<void> {
  const inputEl = event.target as HTMLInputElement
  const files = Array.from(inputEl.files ?? [])
  inputEl.value = ''
  const skill = editing.value
  if (!skill || files.length === 0) return
  assetUploading.value = true
  try {
    for (const file of files) {
      const uploaded = await uploadFile(file)
      const relative = withPath
        ? (file as File & { webkitRelativePath?: string }).webkitRelativePath ||
          file.name
        : file.name
      await addSkillFile(skill.id, uploaded.id, relative)
    }
    await loadAttachments(skill.id)
    app.notify('success', `已添加 ${files.length} 个资料文件`)
  } catch (err) {
    app.notifyError(err)
  } finally {
    assetUploading.value = false
  }
}

async function removeAttachment(item: SkillFileInfo): Promise<void> {
  const skill = editing.value
  if (!skill) return
  try {
    await removeSkillFile(skill.id, item.file_id)
    await loadAttachments(skill.id)
  } catch (err) {
    app.notifyError(err)
  }
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    skills.value = await listSkills()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function resetFormSnapshot(): void {
  formSnapshot.value = JSON.stringify(form.value)
}

function openCreate(): void {
  editing.value = null
  attachments.value = []
  form.value = { name: '', description: '', instruction: '', system_prompt: '' }
  resetFormSnapshot()
  modalOpen.value = true
}

function openEdit(skill: Skill): void {
  editing.value = skill
  form.value = {
    name: skill.name,
    description: skill.description ?? '',
    instruction: skill.instruction,
    system_prompt: skill.system_prompt,
  }
  resetFormSnapshot()
  modalOpen.value = true
  void loadAttachments(skill.id)
}

function requestClose(): void {
  if (saving.value) return
  if (formDirty.value) {
    discardOpen.value = true
    return
  }
  modalOpen.value = false
}

function discardChanges(): void {
  discardOpen.value = false
  modalOpen.value = false
}

async function submit(): Promise<void> {
  const name = form.value.name.trim()
  const instruction = form.value.instruction.trim()
  if (!name || !instruction) {
    app.notify('error', '名称与指令不能为空')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await updateSkill(editing.value.id, {
        name,
        description: form.value.description,
        instruction,
        system_prompt: form.value.system_prompt,
      })
      app.notify('success', 'Skill 已更新')
    } else {
      await createSkill({
        name,
        description: form.value.description,
        instruction,
        system_prompt: form.value.system_prompt,
      })
      app.notify('success', 'Skill 已添加')
    }
    modalOpen.value = false
    await load()
  } catch (err) {
    app.notifyError(err)
  } finally {
    saving.value = false
  }
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value
  if (!target) return
  deleting.value = true
  try {
    await deleteSkill(target.id)
    app.notify('success', `已删除「${target.name}」`)
    deleteTarget.value = null
    await load()
  } catch (err) {
    app.notifyError(err)
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="skills-view">
    <header class="page-head">
      <div>
        <h1 class="page-head__title">Skill Library</h1>
        <p class="page-head__desc">
          全局 Skill 库。Task 内部只能引用这里添加的 Skill；执行时由所选 Skill 决定输出。
        </p>
      </div>
      <button type="button" class="btn btn--primary btn--sm" @click="openCreate">
        <AppIcon name="plus" :size="15" />
        添加 Skill
      </button>
    </header>

    <LoadingState v-if="loading" label="正在加载 Skill…" />

    <div v-else-if="error" class="panel panel--error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">Skill 加载失败</p>
        <p class="panel--error__desc">{{ error }}</p>
      </div>
      <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
    </div>

    <EmptyState
      v-else-if="skills.length === 0"
      icon="sparkles"
      title="还没有 Skill"
      description="添加一个 Skill，定义它的指令与输出要求，然后在 Task 对话中引用。"
    >
      <button type="button" class="btn btn--primary" @click="openCreate">
        <AppIcon name="plus" :size="16" />
        添加 Skill
      </button>
    </EmptyState>

    <ul v-else class="skill-cards">
      <li v-for="skill in skills" :key="skill.id" class="skill-card">
        <header class="skill-card__head">
          <span class="skill-card__icon"><AppIcon name="sparkles" :size="16" /></span>
          <div class="skill-card__title-wrap">
            <h2 class="skill-card__title">
              <button type="button" class="skill-card__title-button" @click="openEdit(skill)">
                {{ skill.name }}
              </button>
            </h2>
            <span v-if="skill.is_builtin" class="chip chip--muted">内置</span>
          </div>
          <div class="skill-card__actions">
            <button type="button" class="btn btn--ghost btn--sm" @click="deleteTarget = skill">
              删除
            </button>
          </div>
        </header>
        <button type="button" class="skill-card__content" @click="openEdit(skill)">
          <span class="skill-card__desc">{{ skill.description || '（无描述）' }}</span>
          <span class="skill-card__instruction">{{ skill.instruction }}</span>
        </button>
        <p class="skill-card__meta">更新于 {{ formatDateTime(skill.updated_at) }}</p>
      </li>
    </ul>

    <Modal
      :open="modalOpen"
      :title="editing ? '编辑 Skill' : '添加 Skill'"
      width="560px"
      :dismissible="!saving"
      @close="requestClose"
    >
      <div class="form-stack">
        <label class="field">
          <span class="field__label">名称</span>
          <input v-model="form.name" class="input" type="text" maxlength="100" />
        </label>
        <label class="field">
          <span class="field__label">描述</span>
          <input v-model="form.description" class="input" type="text" maxlength="500" />
        </label>
        <label class="field">
          <span class="field__label">指令 / 输出要求</span>
          <textarea v-model="form.instruction" class="textarea" rows="5" />
        </label>
        <label class="field">
          <span class="field__label">System Prompt（可选）</span>
          <textarea v-model="form.system_prompt" class="textarea" rows="3" />
        </label>

        <div class="field">
          <div class="skill-assets__head">
            <span class="field__label">资料文件 / 文件夹</span>
            <div class="skill-assets__actions">
              <button
                type="button"
                class="btn btn--ghost btn--sm"
                :disabled="!editing || assetUploading"
                @click="fileInput?.click()"
              >
                <AppIcon name="upload" :size="13" />
                上传文件
              </button>
              <button
                type="button"
                class="btn btn--ghost btn--sm"
                :disabled="!editing || assetUploading"
                @click="folderInput?.click()"
              >
                <AppIcon name="folder" :size="13" />
                上传文件夹
              </button>
            </div>
          </div>
          <p v-if="!editing" class="skill-assets__hint">保存 Skill 后，可以在编辑里添加文件或文件夹。</p>
          <ul v-else-if="attachments.length" class="skill-assets__list">
            <li v-for="item in attachments" :key="item.file_id" class="skill-assets__item">
              <AppIcon name="file" :size="12" />
              <button
                type="button"
                class="skill-assets__path skill-assets__path--button"
                @click="previewFileId = item.file_id"
              >
                {{ item.path || item.filename }}
              </button>
              <button
                type="button"
                class="btn btn--ghost btn--sm"
                @click="removeAttachment(item)"
              >
                移除
              </button>
            </li>
          </ul>
          <p v-else class="skill-assets__hint">还没有资料文件；可上传模板、参考资料或整个文件夹。</p>
          <input
            ref="fileInput"
            class="hidden-input"
            type="file"
            multiple
            accept=".pdf,.md,.markdown,.txt"
            @change="onAssetSelected($event, false)"
          />
          <input
            ref="folderInput"
            class="hidden-input"
            type="file"
            multiple
            webkitdirectory
            @change="onAssetSelected($event, true)"
          />
        </div>
      </div>
      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="saving" @click="requestClose">
          取消
        </button>
        <button type="button" class="btn btn--primary" :disabled="saving" @click="submit">
          保存
        </button>
      </template>
    </Modal>

    <Modal
      :open="Boolean(deleteTarget)"
      title="删除 Skill"
      width="420px"
      :dismissible="!deleting"
      @close="deleteTarget = null"
    >
      <p class="delete-copy">
        删除「{{ deleteTarget?.name }}」后，Task 中的引用会一并移除；已产生的 Execution 快照不受影响。
      </p>
      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="deleting" @click="deleteTarget = null">
          取消
        </button>
        <button type="button" class="btn btn--primary" :disabled="deleting" @click="confirmDelete">
          删除
        </button>
      </template>
    </Modal>

    <FilePreviewModal
      :file-id="previewFileId"
      @close="previewFileId = null"
    />

    <ConfirmDialog
      :open="discardOpen"
      title="放弃未保存的修改？"
      message="当前 Skill 的修改尚未保存。关闭后，这些修改会丢失。"
      confirm-label="放弃修改"
      cancel-label="继续编辑"
      @confirm="discardChanges"
      @close="discardOpen = false"
    />
  </div>
</template>

<style scoped>
.skills-view {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border);
}

.page-head__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 600;
  letter-spacing: -0.035em;
  line-height: 1.15;
}

.page-head__desc {
  margin: 8px 0 0;
  font-size: 13.5px;
  line-height: 1.65;
  color: var(--text-secondary);
}

.skill-cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 28px 32px;
}

.skill-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 2px 14px;
  border: 0;
  border-top: 1px solid var(--border);
  border-radius: 0;
  background: transparent;
}

.skill-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.skill-card__icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--accent);
}

.skill-card__title-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.skill-card__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.015em;
}

.skill-card__title-button {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  letter-spacing: inherit;
  text-align: left;
  cursor: pointer;
}

.skill-card__title-button:hover {
  color: var(--accent);
}

.skill-card__content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.skill-card__content:hover .skill-card__desc,
.skill-card__content:hover .skill-card__instruction {
  color: var(--text);
}

.skill-card__actions {
  margin-left: auto;
  display: flex;
  gap: 2px;
}

.skill-card__desc {
  display: block;
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.skill-card__instruction {
  display: block;
  margin: 0;
  padding: 8px 0 8px 12px;
  border-left: 1px solid var(--border-strong);
  border-radius: 0;
  background: transparent;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.skill-card__meta {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.form-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skill-assets__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.skill-assets__actions {
  display: flex;
  gap: 4px;
}

.skill-assets__hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-faint);
}

.skill-assets__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 140px;
  overflow-y: auto;
}

.skill-assets__item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.skill-assets__path {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skill-assets__path--button {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.skill-assets__path--button:hover {
  color: var(--accent);
}

.hidden-input {
  display: none;
}

.delete-copy {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--text-secondary);
}
</style>
