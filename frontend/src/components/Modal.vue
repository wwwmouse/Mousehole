<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

import AppIcon from '@/components/AppIcon.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    width?: string
    dismissible?: boolean
    zIndex?: number
  }>(),
  { width: '520px', dismissible: true, zIndex: undefined },
)

const emit = defineEmits<{ close: [] }>()

function requestClose(): void {
  if (props.dismissible) emit('close')
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') requestClose()
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      window.addEventListener('keydown', onKeydown)
      document.body.style.overflow = 'hidden'
    } else {
      window.removeEventListener('keydown', onKeydown)
      document.body.style.overflow = ''
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="modal-backdrop"
        :style="zIndex ? { zIndex } : undefined"
        @mousedown.self="requestClose"
      >
        <section
          class="modal-panel"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
          :style="{ width }"
        >
          <header class="modal-header">
            <h2 class="modal-title">{{ title }}</h2>
            <button
              v-if="dismissible"
              type="button"
              class="modal-close"
              aria-label="关闭"
              @click="requestClose"
            >
              <AppIcon name="close" :size="16" />
            </button>
          </header>
          <div class="modal-body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="modal-footer">
            <slot name="footer" />
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 150;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 8vh 24px 24px;
  overflow-y: auto;
  background: rgba(5, 7, 10, 0.66);
  backdrop-filter: blur(2px);
}

.modal-panel {
  display: flex;
  flex-direction: column;
  max-width: calc(100vw - 48px);
  max-height: 84vh;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  background: var(--bg-raised);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.modal-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.modal-close {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.modal-close:hover {
  background: var(--bg-hover);
  color: var(--text);
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  background: var(--bg-subtle);
  flex-shrink: 0;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.15s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-panel,
.modal-leave-active .modal-panel {
  transition: transform 0.15s ease;
}

.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: translateY(-8px) scale(0.99);
}
</style>
