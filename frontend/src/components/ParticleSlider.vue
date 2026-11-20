<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: number
    min: number
    max: number
    step?: number
    label: string
    hint?: string
    unit?: string
    minLabel?: string
    maxLabel?: string
    format?: (value: number) => string
  }>(),
  { step: 1, unit: '', minLabel: '', maxLabel: '', hint: '' },
)

const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

const trackRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  maxLife: number
  size: number
  hue: number
}

let particles: Particle[] = []
let raf = 0
let active = false

const ratio = computed(() =>
  Math.min(
    1,
    Math.max(0, (props.modelValue - props.min) / (props.max - props.min)),
  ),
)

const display = computed(() =>
  props.format ? props.format(props.modelValue) : String(props.modelValue),
)

function updateValue(event: Event): void {
  const next = Number((event.target as HTMLInputElement).value)
  emit('update:modelValue', next)
  spawn(6)
}

function spawn(count: number): void {
  const track = trackRef.value
  if (!track) return
  const rect = track.getBoundingClientRect()
  const x = rect.width * ratio.value
  for (let index = 0; index < count; index += 1) {
    particles.push({
      x,
      y: rect.height / 2 + (Math.random() - 0.5) * 8,
      vx: (Math.random() - 0.5) * 1.2,
      vy: -Math.random() * 0.9 - 0.2,
      life: 0,
      maxLife: 28 + Math.random() * 22,
      size: 0.8 + Math.random() * 1.6,
      hue: 210 + Math.random() * 40,
    })
    if (particles.length > 90) particles.shift()
  }
  if (!raf) raf = requestAnimationFrame(animate)
}

function animate(): void {
  const canvas = canvasRef.value
  const track = trackRef.value
  if (!canvas || !track) {
    raf = 0
    return
  }
  const rect = track.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  if (canvas.width !== rect.width * dpr || canvas.height !== rect.height * dpr) {
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
  }
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    raf = 0
    return
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, rect.width, rect.height)

  particles = particles.filter((particle) => particle.life < particle.maxLife)
  for (const particle of particles) {
    particle.life += 1
    particle.x += particle.vx
    particle.y += particle.vy
    particle.vy += 0.012
    const alpha = Math.max(0, 1 - particle.life / particle.maxLife)
    ctx.beginPath()
    ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2)
    ctx.fillStyle = `hsla(${particle.hue}, 90%, 70%, ${alpha * 0.9})`
    ctx.fill()
  }

  if (active) spawn(1)
  raf = particles.length > 0 || active ? requestAnimationFrame(animate) : 0
}

function onPointerDown(): void {
  active = true
  spawn(12)
}

function onPointerUp(): void {
  active = false
}

function onHover(): void {
  spawn(1)
}

onMounted(() => {
  spawn(8)
})

onBeforeUnmount(() => {
  active = false
  if (raf) cancelAnimationFrame(raf)
  raf = 0
})
</script>

<template>
  <div class="pslider">
    <div class="pslider__head">
      <div class="pslider__labels">
        <span class="pslider__label">{{ label }}</span>
        <span v-if="hint" class="pslider__hint">{{ hint }}</span>
      </div>
      <span class="pslider__value">{{ display }}{{ unit }}</span>
    </div>
    <div
      ref="trackRef"
      class="pslider__track"
      @pointerenter="onHover"
      @pointerdown="onPointerDown"
      @pointerup="onPointerUp"
      @pointerleave="onPointerUp"
    >
      <div class="pslider__fill" :style="{ width: `${ratio * 100}%` }" />
      <canvas ref="canvasRef" class="pslider__canvas" aria-hidden="true" />
      <div class="pslider__thumb" :style="{ left: `${ratio * 100}%` }" />
      <input
        class="pslider__input"
        type="range"
        :min="min"
        :max="max"
        :step="step"
        :value="modelValue"
        :aria-label="label"
        @input="updateValue"
      />
    </div>
    <div class="pslider__bounds">
      <span>{{ minLabel }}</span>
      <span>{{ maxLabel }}</span>
    </div>
  </div>
</template>

<style scoped>
.pslider {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pslider__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.pslider__labels {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.pslider__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.pslider__hint {
  font-size: 10px;
  line-height: 1.4;
  color: var(--text-faint);
}

.pslider__value {
  font-family: var(--font-mono);
  color: var(--accent);
}

.pslider__track {
  position: relative;
  height: 22px;
  display: flex;
  align-items: center;
  touch-action: none;
}

.pslider__track::before {
  content: '';
  position: absolute;
  inset: 50% 0 auto;
  height: 4px;
  transform: translateY(-50%);
  border-radius: 999px;
  background: var(--bg-hover);
  box-shadow: inset 0 0 0 1px var(--border);
}

.pslider__fill {
  position: absolute;
  left: 0;
  top: 50%;
  height: 4px;
  transform: translateY(-50%);
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), #9b8cff);
  box-shadow: 0 0 10px color-mix(in srgb, var(--accent) 45%, transparent);
}

.pslider__canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.pslider__thumb {
  position: absolute;
  top: 50%;
  width: 12px;
  height: 12px;
  margin-left: -6px;
  transform: translateY(-50%);
  border-radius: 50%;
  background: var(--bg);
  border: 2px solid var(--accent);
  box-shadow: 0 0 12px color-mix(in srgb, var(--accent) 55%, transparent);
  pointer-events: none;
}

.pslider__input {
  position: absolute;
  inset: 0;
  width: 100%;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}

.pslider__bounds {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-faint);
}
</style>
