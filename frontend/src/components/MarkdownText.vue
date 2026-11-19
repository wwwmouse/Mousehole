<script setup lang="ts">
import { computed } from 'vue'

import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ text: string }>()

const html = computed(() => renderMarkdown(props.text))
</script>

<template>
  <div class="md-content" v-html="html" />
</template>

<style scoped>
.md-content {
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.md-content :deep(h1),
.md-content :deep(h2),
.md-content :deep(h3),
.md-content :deep(h4),
.md-content :deep(h5),
.md-content :deep(h6) {
  margin: 20px 0 8px;
  color: var(--text);
  font-weight: 600;
  line-height: 1.4;
}

.md-content :deep(h1) {
  font-size: 19px;
}

.md-content :deep(h2) {
  font-size: 17px;
}

.md-content :deep(h3) {
  font-size: 15px;
}

.md-content :deep(h4),
.md-content :deep(h5),
.md-content :deep(h6) {
  font-size: 14px;
}

.md-content :deep(p) {
  margin: 0 0 10px;
}

.md-content :deep(ul),
.md-content :deep(ol) {
  margin: 0 0 12px;
  padding-left: 22px;
}

.md-content :deep(li) {
  margin-bottom: 4px;
}

.md-content :deep(blockquote) {
  margin: 0 0 12px;
  padding: 6px 14px;
  border-left: 2px solid var(--accent-border);
  background: var(--bg-subtle);
  color: var(--text-secondary);
}

.md-content :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--bg-active);
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--text);
}

.md-content :deep(pre.md-code) {
  margin: 0 0 14px;
  padding: 12px 14px;
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  line-height: 1.6;
}

.md-content :deep(pre.md-code code) {
  padding: 0;
  background: none;
  font-size: 12.5px;
  white-space: pre;
}

.md-content :deep(strong) {
  color: var(--text);
  font-weight: 600;
}
</style>
