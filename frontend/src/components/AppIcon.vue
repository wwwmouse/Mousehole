<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    size?: number
    strokeWidth?: number
  }>(),
  { size: 18, strokeWidth: 1.7 },
)

const ICONS: Record<string, string[]> = {
  home: ['M3.5 10.5 12 3.5l8.5 7', 'M5.5 9.5V20a.5.5 0 0 0 .5.5h12a.5.5 0 0 0 .5-.5V9.5'],
  folder: [
    'M3 7.5A1.5 1.5 0 0 1 4.5 6H9l2 2.5h8.5A1.5 1.5 0 0 1 21 10v8.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z',
  ],
  library: ['M4.5 5.5A2.5 2.5 0 0 1 7 3h12v18H7a2.5 2.5 0 0 1-2.5-2.5z', 'M8.5 3v18'],
  settings: [
    'M12 15.25a3.25 3.25 0 1 0 0-6.5 3.25 3.25 0 0 0 0 6.5Z',
    'M19.4 13.4c.06.4.06.8 0 1.2l1.5 1.2-1.7 3-1.9-.7c-.3.3-.7.5-1.1.6l-.3 2h-3.4l-.3-2c-.4-.1-.8-.3-1.1-.6l-1.9.7-1.7-3 1.5-1.2a4.6 4.6 0 0 1 0-1.2l-1.5-1.2 1.7-3 1.9.7c.3-.3.7-.5 1.1-.6l.3-2h3.4l.3 2c.4.1.8.3 1.1.6l1.9-.7 1.7 3z',
  ],
  panel: ['M4.5 4.5h15v15h-15z', 'M9.5 4.5v15'],
  plus: ['M12 5v14', 'M5 12h14'],
  search: ['M11 18.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15Z', 'm21 21-4.2-4.2'],
  upload: ['M12 16V4', 'm6.5 9.5 5.5-5.5 5.5 5.5', 'M4.5 20h15'],
  trash: ['M4 7h16', 'M10 11v6', 'M14 11v6', 'M6.5 7 7.5 20h9L17.5 7', 'M9.5 7V4h5v3'],
  close: ['m6 6 12 12', 'M18 6 6 18'],
  'chevron-right': ['m9.5 6 6 6-6 6'],
  'chevron-left': ['m14.5 6-6 6 6 6'],
  'chevron-down': ['m6 9.5 6 6 6-6'],
  'arrow-left': ['M19 12H5', 'm11 6-6 6 6 6'],
  file: ['M14 3.5H7a1.5 1.5 0 0 0-1.5 1.5v14A1.5 1.5 0 0 0 7 20.5h10a1.5 1.5 0 0 0 1.5-1.5V8z', 'M14 3.5V8h4.5'],
  check: ['m5 12.5 4.5 4.5L19 7'],
  flag: ['M5 21V4', 'M5 4h14l-2.5 4L19 12H5'],
  filter: ['M4 5h16l-6 8v6l-4 2v-8z'],
  alert: ['M12 8.5v5', 'M12 17v.5', 'M10.3 4.4 2.9 17a1.8 1.8 0 0 0 1.6 2.7h15a1.8 1.8 0 0 0 1.6-2.7L13.7 4.4a1.9 1.9 0 0 0-3.4 0Z'],
  info: ['M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17Z', 'M12 11v5.5', 'M12 7.8v.4'],
  archive: ['M3.5 5.5h17v3.5h-17z', 'M5.5 9v9.5A1.5 1.5 0 0 0 7 20h10a1.5 1.5 0 0 0 1.5-1.5V9', 'M10 13h4'],
  refresh: ['M19.5 11.5A7.5 7.5 0 1 0 17.2 17', 'M19.5 5.5v6h-6'],
  edit: ['M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17z', 'm14.5 7.5 2.5 2.5'],
  clock: ['M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17Z', 'M12 7.5V12l3 1.8'],
  sparkles: ['M12 3.5 13.7 8.3 18.5 10 13.7 11.7 12 16.5 10.3 11.7 5.5 10 10.3 8.3z', 'M18 15.5l.8 1.7 1.7.8-1.7.8-.8 1.7-.8-1.7-1.7-.8 1.7-.8z'],
  send: ['M20.5 3.5 10.5 13.5', 'M20.5 3.5 14 20.5l-3.5-7-7-3.5z'],
  external: ['M14 4.5h5.5V10', 'M19.5 4.5 10 14', 'M18.5 13.5v5a1.5 1.5 0 0 1-1.5 1.5H5.5A1.5 1.5 0 0 1 4 18.5V7a1.5 1.5 0 0 1 1.5-1.5h5'],
  chart: ['M4.5 20V10.5', 'M10 20V4.5', 'M15.5 20v-6.5', 'M21 20H3'],
  database: ['M12 8.5c4.4 0 8-1.3 8-2.9S16.4 2.7 12 2.7 4 4 4 5.6s3.6 2.9 8 2.9Z', 'M4 5.6v12.8c0 1.6 3.6 2.9 8 2.9s8-1.3 8-2.9V5.6', 'M4 12c0 1.6 3.6 2.9 8 2.9s8-1.3 8-2.9'],
  more: ['M5 12h.01', 'M12 12h.01', 'M19 12h.01'],
}

const segments = computed(() => ICONS[props.name] ?? [])
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="(segment, index) in segments" :key="index" :d="segment" />
  </svg>
</template>
