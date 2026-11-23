import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vitest/config'

/**
 * Unit tests: Vitest + Vue runtime only. Components are not mounted here —
 * the extracted composables / pure utilities are tested directly, so no DOM
 * environment and no network access are required.
 */
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['tests/unit/**/*.spec.ts'],
    restoreMocks: true,
  },
})
