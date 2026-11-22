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

function niceCeiling(value: number): number {
  if (value <= 10) return Math.max(4, Math.ceil((value * 1.2) / 2) * 2)
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const step = magnitude / 2
  return Math.ceil((value * 1.18) / step) * step
}

const maxValue = computed(() => niceCeiling(Math.max(0, ...props.values)))
const midValue = computed(() => Math.round(maxValue.value / 2))

function compact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}m`
  if (value >= 1_000) return `${(value / 1_000).toFixed(value >= 10_000 ? 0 : 1)}k`
  return String(value)
}

function barHeight(value: number): string {
  // 18% headroom keeps the highest day from touching the top rule.
  const ratio = value / maxValue.value
  return `${Math.max(2, Math.round(ratio * 100))}%`
}
</script>

<template>
  <div class="bar-chart" role="img" aria-label="近 7 天统计柱状图">
    <div class="bar-chart__axis" aria-hidden="true">
      <span>{{ compact(maxValue) }}</span>
      <span>{{ compact(midValue) }}</span>
      <span>0</span>
    </div>

    <div class="bar-chart__plot">
      <div class="bar-chart__grid" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div class="bar-chart__bars">
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
    </div>
  </div>
</template>

<style scoped>
.bar-chart {
  display: flex;
  flex: 1;
  gap: 10px;
  min-height: 190px;
  padding-top: 6px;
}

.bar-chart__axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  width: 34px;
  padding-bottom: 18px;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.02em;
  line-height: 1;
  color: var(--text-muted);
  text-align: right;
}

.bar-chart__plot {
  position: relative;
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.bar-chart__grid {
  position: absolute;
  inset: 0 0 18px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  pointer-events: none;
}

.bar-chart__grid span {
  width: 100%;
  border-top: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
}

.bar-chart__bars {
  display: flex;
  flex: 1;
  align-items: stretch;
  gap: 8px;
  min-height: 0;
  padding-bottom: 0;
}

.bar-chart__item {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  height: 100%;
}

.bar-chart__track {
  display: flex;
  flex: 1;
  align-items: flex-end;
  width: 100%;
  min-height: 0;
}

.bar-chart__bar {
  width: 100%;
  min-height: 2px;
  border-radius: 1px 1px 0 0;
  background: var(--accent);
  transition: height 0.25s ease;
}

.bar-chart__label {
  height: 18px;
  padding-top: 5px;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.02em;
  color: var(--text-muted);
  white-space: nowrap;
}
</style>
