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
          tabindex="0"
        >
          <span class="bar-chart__tooltip">
            {{ labels[index] }} · {{ format(value) }}
          </span>
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
  width: 36px;
  padding-bottom: 20px;
  font-family: var(--font-mono);
  font-size: 12px;
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
  inset: 0 0 20px;
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
  position: relative;
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  outline: none;
}

.bar-chart__tooltip {
  position: absolute;
  bottom: calc(100% + 7px);
  left: 50%;
  z-index: 5;
  padding: 5px 8px;
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-sm);
  background: var(--bg-raised);
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.01em;
  white-space: nowrap;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  opacity: 0;
  visibility: hidden;
  transform: translate(-50%, 4px);
  transition:
    opacity 0.14s ease,
    transform 0.14s ease,
    visibility 0.14s ease;
  pointer-events: none;
}

.bar-chart__item:hover .bar-chart__tooltip,
.bar-chart__item:focus-visible .bar-chart__tooltip {
  opacity: 1;
  visibility: visible;
  transform: translate(-50%, 0);
}

.bar-chart__item:focus-visible .bar-chart__bar {
  filter: brightness(1.12);
}

.bar-chart__track {
  display: flex;
  flex: 1;
  justify-content: center;
  align-items: flex-end;
  width: 100%;
  min-height: 0;
}

.bar-chart__bar {
  width: 58%;
  max-width: 46px;
  min-height: 2px;
  border-radius: 1px 1px 0 0;
  background: var(--accent);
  transition: height 0.25s ease;
}

.bar-chart__label {
  height: 20px;
  padding-top: 6px;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.01em;
  color: var(--text-secondary);
  text-align: center;
  white-space: nowrap;
}
</style>
