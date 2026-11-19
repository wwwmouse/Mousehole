/**
 * Capability fallback shim (loaded only when esbuild cannot spawn its child
 * process, e.g. inside a hardened sandbox).
 *
 * @vitejs/plugin-vue imports `transformWithEsbuild` from "vite" and uses it to
 * transpile the TypeScript emitted by <script setup lang="ts">. Redirect that
 * single import to this module so the SFC TypeScript is transpiled in-process
 * by the TypeScript compiler instead. Everything else is re-exported unchanged.
 */

import ts from 'typescript'
import * as vite from 'vite'

export * from 'vite'
export { formatPostcssSourceMap, isCSSRequest, normalizePath } from 'vite'

const emptyMap = { mappings: '' }

export async function transformWithEsbuild(code, filename, options = {}, inMap) {
  if (typeof code !== 'string') {
    return { code, map: inMap ?? emptyMap }
  }
  const loader = options.loader ?? 'js'
  let output = code
  if (loader === 'ts' || loader === 'tsx') {
    const result = ts.transpileModule(code, {
      fileName: filename,
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.ESNext,
        jsx: loader === 'tsx' ? ts.JsxEmit.Preserve : undefined,
        esModuleInterop: true,
        isolatedModules: true,
      },
      reportDiagnostics: false,
    })
    output = result.outputText
  }
  return {
    code: output,
    // Source maps are not part of this build; keep the incoming map when given.
    map: inMap ?? emptyMap,
  }
}
