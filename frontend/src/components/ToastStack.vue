<script setup lang="ts">
import AppIcon from '@/components/AppIcon.vue'
import { useAppStore } from '@/stores/app'

const app = useAppStore()

const icons: Record<string, string> = {
  success: 'check',
  error: 'alert',
  info: 'info',
}
</script>

<template>
  <div class="toast-stack" aria-live="polite" aria-atomic="false">
    <TransitionGroup name="toast">
      <div v-for="toast in app.toasts" :key="toast.id" class="toast" :data-kind="toast.kind" role="status">
        <AppIcon class="toast__icon" :name="icons[toast.kind] ?? 'info'" :size="16" />
        <div class="toast__body">
          <p class="toast__message">{{ toast.message }}</p>
          <p v-if="toast.detail" class="toast__detail">{{ toast.detail }}</p>
        </div>
        <button type="button" class="toast__close" aria-label="关闭提示" @click="app.dismissToast(toast.id)">
          <AppIcon name="close" :size="14" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(380px, calc(100vw - 40px));
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 12px 12px 14px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  background: var(--bg-raised);
  box-shadow: var(--shadow-lg);
  pointer-events: auto;
}

.toast[data-kind='success'] {
  border-color: rgba(74, 194, 107, 0.4);
}

.toast[data-kind='error'] {
  border-color: rgba(242, 105, 92, 0.45);
}

.toast__icon {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--text-muted);
}

.toast[data-kind='success'] .toast__icon {
  color: var(--success);
}

.toast[data-kind='error'] .toast__icon {
  color: var(--danger);
}

.toast[data-kind='info'] .toast__icon {
  color: var(--accent);
}

.toast__body {
  flex: 1;
  min-width: 0;
}

.toast__message {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text);
  overflow-wrap: anywhere;
}

.toast__detail {
  margin: 3px 0 0;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-faint);
  overflow-wrap: anywhere;
}

.toast__close {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.toast__close:hover {
  background: var(--bg-hover);
  color: var(--text);
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.toast-leave-active {
  position: absolute;
}

.toast-move {
  transition: transform 0.18s ease;
}
</style>
