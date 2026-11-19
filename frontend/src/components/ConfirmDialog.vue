<script setup lang="ts">
import Modal from '@/components/Modal.vue'

withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
    danger?: boolean
    busy?: boolean
  }>(),
  {
    confirmLabel: '确认',
    cancelLabel: '取消',
    danger: false,
    busy: false,
  },
)

const emit = defineEmits<{ confirm: []; close: [] }>()
</script>

<template>
  <Modal :open="open" :title="title" :dismissible="!busy" width="460px" @close="emit('close')">
    <p class="confirm-message">{{ message }}</p>
    <slot />
    <template #footer>
      <button type="button" class="btn btn--ghost" :disabled="busy" @click="emit('close')">
        {{ cancelLabel }}
      </button>
      <button
        type="button"
        class="btn"
        :class="danger ? 'btn--danger' : 'btn--primary'"
        :disabled="busy"
        @click="emit('confirm')"
      >
        <span v-if="busy" class="spinner spinner--sm" aria-hidden="true" />
        {{ confirmLabel }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.confirm-message {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.65;
  white-space: pre-wrap;
}
</style>
