<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import Modal from '@/components/Modal.vue'
import { createProject } from '@/api/endpoints'
import type { Project } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'

const props = defineProps<{ open: boolean }>()

const emit = defineEmits<{ close: []; created: [project: Project] }>()

const app = useAppStore()

const form = reactive({ name: '', description: '' })
const submitting = ref(false)
const formError = ref<string | null>(null)

watch(
  () => props.open,
  (open) => {
    if (open) {
      form.name = ''
      form.description = ''
      formError.value = null
      submitting.value = false
    }
  },
)

async function submit(): Promise<void> {
  const name = form.name.trim()
  if (!name) {
    formError.value = '请填写项目名称'
    return
  }
  submitting.value = true
  formError.value = null
  try {
    const project = await createProject({
      workspace_id: app.currentWorkspace?.id,
      name,
      description: form.description.trim() ? form.description.trim() : null,
    })
    app.notify('success', `项目「${project.name}」已创建`)
    emit('created', project)
  } catch (error) {
    formError.value = errorMessage(error)
    app.notifyError(error)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Modal :open="open" title="新建 Project" width="520px" :dismissible="!submitting" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <label class="field">
        <span class="field__label">项目名称</span>
        <input
          v-model="form.name"
          class="input"
          type="text"
          maxlength="200"
          placeholder="例如：Agent Learning"
          autofocus
        />
      </label>
      <label class="field">
        <span class="field__label">描述 <span class="field__hint">（可选）</span></span>
        <textarea
          v-model="form.description"
          class="textarea"
          rows="4"
          maxlength="4000"
          placeholder="这个项目要长期跟进什么？"
        />
      </label>
      <p v-if="formError" class="form-error">{{ formError }}</p>
    </form>

    <template #footer>
      <button type="button" class="btn btn--ghost" :disabled="submitting" @click="emit('close')">取消</button>
      <button type="button" class="btn btn--primary" :disabled="submitting" @click="submit">
        <span v-if="submitting" class="spinner spinner--sm" aria-hidden="true" />
        {{ submitting ? '创建中…' : '创建项目' }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
  color: var(--text-faint);
  font-weight: 400;
}

.form-error {
  margin: 0;
  color: var(--danger);
  font-size: 12.5px;
}
</style>
