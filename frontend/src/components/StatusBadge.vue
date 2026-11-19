<script setup lang="ts">
import { computed } from 'vue'

import { projectStatusLabel, taskStatusLabel } from '@/utils/format'

type BadgeKind = 'project' | 'task' | 'file' | 'custom'

const props = withDefaults(
  defineProps<{
    status: string
    kind?: BadgeKind
    label?: string
    dot?: boolean
  }>(),
  { kind: 'custom', label: undefined, dot: true },
)

const tone = computed(() => {
  const status = props.status
  if (status === 'active') return 'active'
  if (status === 'completed' || status === 'parsed' || status === 'ready') return 'success'
  if (status === 'archived' || status === 'deleted') return 'muted'
  if (status === 'failed' || status === 'error') return 'danger'
  if (status === 'processing' || status === 'pending' || status === 'running') return 'warning'
  return 'neutral'
})

const text = computed(() => {
  if (props.label) return props.label
  if (props.kind === 'project') return projectStatusLabel(props.status)
  if (props.kind === 'task') return taskStatusLabel(props.status)
  return props.status
})
</script>

<template>
  <span class="status-badge" :data-tone="tone">
    <span v-if="dot" class="status-badge__dot" aria-hidden="true" />
    {{ text }}
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-raised);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}

.status-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.85;
}

.status-badge[data-tone='active'] {
  color: var(--accent);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}

.status-badge[data-tone='success'] {
  color: var(--success);
  border-color: rgba(74, 194, 107, 0.35);
  background: var(--success-soft);
}

.status-badge[data-tone='warning'] {
  color: var(--warning);
  border-color: rgba(217, 164, 65, 0.35);
  background: var(--warning-soft);
}

.status-badge[data-tone='danger'] {
  color: var(--danger);
  border-color: rgba(242, 105, 92, 0.35);
  background: var(--danger-soft);
}

.status-badge[data-tone='muted'] {
  color: var(--text-muted);
  background: var(--bg-subtle);
}

.status-badge[data-tone='neutral'] {
  color: var(--text-secondary);
}
</style>
