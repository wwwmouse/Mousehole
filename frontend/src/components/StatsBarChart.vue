<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    values: number[]
    labels: string[]
    format?: (value: number) => string
  }>(),
  { format: (value: number) => String(value) },
)

const maxValue = computed(() => Math.max(1, ...props.values))

function barHeight(value: number): string {
  const ratio = value / maxValue.value
  return `${Math.max(4, Math.round(ratio * 100))}%`
}
</script>

<template>
  <div class="bar-chart" role="img" aria-label="近 7 天统计柱状图">
    <div
      v-for="(value, index) in values"
      :key="labels[index] ?? index"
      class="bar-chart__item"
      :title="`${labels[index] ?? ''}: ${format(value)}`"
    >
      <div class="bar-chart__track">
        <div class="bar-chart__bar" :style="{ height: barHeight(value) }" />
      </div>
      <span class="bar-chart__label">{{ labels[index] }}</span>
    </div>
  </div>
</template>

<style scoped>
.bar-chart {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 84px;
  padding-top: 6px;
}

.bar-chart__item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.bar-chart__track {
  display: flex;
  align-items: flex-end;
  width: 100%;
  height: 58px;
  border-radius: 3px;
  background: color-mix(in srgb, var(--accent) 6%, transparent);
}

.bar-chart__bar {
  width: 100%;
  border-radius: 3px 3px 0 0;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--accent) 95%, white 5%),
    color-mix(in srgb, var(--accent) 55%, transparent)
  );
  transition: height 0.25s ease;
}

.bar-chart__label {
  font-size: 9px;
  color: var(--text-faint);
  white-space: nowrap;
}
</style>
