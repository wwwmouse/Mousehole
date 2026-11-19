<script setup lang="ts">
withDefaults(defineProps<{ label?: string; compact?: boolean }>(), {
  label: '加载中…',
  compact: false,
})
</script>

<template>
  <div class="loading-state" :class="{ 'loading-state--compact': compact }" role="status" aria-live="polite">
    <span class="spinner" aria-hidden="true" />
    <span class="loading-state__label">{{ label }}</span>
  </div>
</template>

<style scoped>
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 16px;
  color: var(--text-muted);
}

.loading-state--compact {
  padding: 16px;
  justify-content: flex-start;
}

.loading-state__label {
  font-size: 13px;
}
</style>
