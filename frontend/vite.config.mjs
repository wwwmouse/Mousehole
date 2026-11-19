import { spawnSync } from 'node:child_process'
import childProcess from 'node:child_process'
import { createRequire } from 'node:module'
import { syncBuiltinESMExports } from 'node:module'
import { fileURLToPath, URL } from 'node:url'

import ts from 'typescript'

const requireFromConfig = createRequire(import.meta.url)

/**
 * Environment capability probes.
 *
 * Vite's normal toolchain launches child processes with piped stdio (esbuild
 * transforms, and a Windows `net use` realpath probe). Some hardened or
 * sandboxed environments forbid that (spawn EPERM). Detect it once and either
 * keep the standard Vite + esbuild toolchain (normal machines, fast path) or
 * enable the fallback wiring below:
 *   - transpile .ts with the TypeScript compiler instead of esbuild
 *   - disable esbuild-based minification
 *   - replace the built-in plugins that call esbuild for define replacement
 *   - reroute @vitejs/plugin-vue's TS transpile through scripts/ shim
 *   - answer Vite's optional Windows `net use` probe without spawning
 */
function spawnWithPipesAvailable() {
  try {
    const result = spawnSync(process.execPath, ['-e', ''], { encoding: 'utf8', timeout: 5000 })
    return !result.error
  } catch {
    return false
  }
}

function esbuildAvailable() {
  try {
    const esbuild = requireFromConfig('esbuild')
    esbuild.transformSync('export const ok = 1', { loader: 'ts', logLevel: 'silent' })
    return true
  } catch {
    return false
  }
}

const canSpawn = spawnWithPipesAvailable()
const hasEsbuild = canSpawn && esbuildAvailable()
const buildMode = process.env.NODE_ENV === 'development' ? 'development' : 'production'

if (!canSpawn) {
  // Vite's windowsSafeRealPathSync() probes `net use` via exec() and lets a
  // spawn failure crash the build. Answer that one optional probe without
  // spawning; every other exec() call is forwarded untouched.
  const originalExec = childProcess.exec
  childProcess.exec = function exec(command, options, callback) {
    if (typeof options === 'function') {
      callback = options
      options = undefined
    }
    if (String(command).trim() === 'net use') {
      if (typeof callback === 'function') {
        queueMicrotask(() => callback(new Error('child process spawn unavailable'), '', ''))
      }
      return undefined
    }
    return originalExec.call(this, command, options, callback)
  }
  syncBuiltinESMExports()

  // Let @vitejs/plugin-vue import a shim instead of Vite's esbuild transformer.
  const nodeModule = await import('node:module')
  if (typeof nodeModule.registerHooks === 'function') {
    const shimUrl = new URL('./scripts/vite-plugin-vue-esbuild-shim.mjs', import.meta.url).href
    nodeModule.registerHooks({
      resolve(specifier, context, nextResolve) {
        if (
          specifier === 'vite' &&
          typeof context.parentURL === 'string' &&
          context.parentURL.includes('@vitejs/plugin-vue')
        ) {
          return { url: shimUrl, shortCircuit: true }
        }
        return nextResolve(specifier, context)
      },
    })
  } else {
    console.warn(
      '[mousehole] Node.js without module.registerHooks cannot run the esbuild-free fallback; build may fail.',
    )
  }
}

function replaceDefines(code) {
  return code
    .replace(/\bglobalThis\.process\.env\.NODE_ENV\b/g, JSON.stringify(buildMode))
    .replace(/\bglobal\.process\.env\.NODE_ENV\b/g, JSON.stringify(buildMode))
    .replace(/\bprocess\.env\.NODE_ENV\b/g, JSON.stringify(buildMode))
    .replace(/\bprocess\.env\b/g, '{}')
    .replace(/\b__VUE_OPTIONS_API__\b/g, 'true')
    .replace(/\b__VUE_PROD_DEVTOOLS__\b/g, 'false')
    .replace(/\b__VUE_PROD_HYDRATION_MISMATCH_DETAILS__\b/g, 'false')
    .replace(/\bimport\.meta\.env\.SSR\b/g, 'false')
    .replace(/\bimport\.meta\.env\.PROD\b/g, String(buildMode === 'production'))
    .replace(/\bimport\.meta\.env\.DEV\b/g, String(buildMode !== 'production'))
    .replace(/\bimport\.meta\.env\.MODE\b/g, JSON.stringify(buildMode))
    .replace(/\bimport\.meta\.env\.BASE_URL\b/g, JSON.stringify('/'))
    .replace(/\bimport\.meta\.hot\b/g, 'undefined')
}

function typescriptFallbackPlugin() {
  return {
    name: 'mousehole:typescript-fallback',
    enforce: 'pre',
    transform(code, id) {
      // Handles both real .ts files and Vue virtual modules such as
      // "App.vue?vue&type=script&setup=true&lang.ts".
      if (!/\.(?:[cm]?tsx?)$/.test(id)) return null
      const result = ts.transpileModule(code, {
        fileName: id,
        compilerOptions: {
          target: ts.ScriptTarget.ES2022,
          module: ts.ModuleKind.ESNext,
          moduleResolution: ts.ModuleResolutionKind.Bundler,
          esModuleInterop: true,
          isolatedModules: true,
          sourceMap: false,
        },
        reportDiagnostics: false,
      })
      return { code: result.outputText, map: null }
    },
  }
}

function defineFallbackPlugin() {
  return {
    name: 'mousehole:define-fallback',
    configResolved(config) {
      if (hasEsbuild) return
      // Built-in plugins that would otherwise invoke esbuild's transform().
      for (const plugin of config.plugins) {
        if (plugin.name !== 'vite:define' && plugin.name !== 'vite:client-inject') continue
        plugin.transform = function defineFallbackTransform(code) {
          if (typeof code !== 'string') return null
          const output = replaceDefines(code)
          return output === code ? null : { code: output, map: null }
        }
      }
    },
  }
}

const { defineConfig } = await import('vite')
const vue = (await import('@vitejs/plugin-vue')).default

// Ask the browser to drop cached/stored data for this origin whenever a
// response actually reaches it; helps recover a dev port previously used by
// another project (stale favicon / service worker / cached index).
function clearSiteDataPlugin() {
  const attach = (server) => {
    server.middlewares.use((req, res, next) => {
      // Only on the one-shot cleanup page: JS there clears Cache Storage and
      // unregisters service workers; this header also clears the HTTP cache.
      if (String(req.url).split('?')[0] === '/cleanup.html') {
        res.setHeader('Clear-Site-Data', '"cache", "storage"')
      }
      next()
    })
  }
  return {
    name: 'mousehole:clear-site-data',
    configureServer: attach,
    configurePreviewServer: attach,
  }
}

export default defineConfig(() => ({
  plugins: [
    clearSiteDataPlugin(),
    vue(),
    ...(hasEsbuild ? [] : [typescriptFallbackPlugin(), defineFallbackPlugin()]),
  ],
  ...(hasEsbuild ? {} : { esbuild: false }),
  ...(hasEsbuild ? {} : { build: { minify: false, cssMinify: false } }),
  // Dependency pre-bundling also uses esbuild; with it unavailable, serve the
  // ESM dependencies directly instead of optimizing them.
  ...(hasEsbuild ? {} : { optimizeDeps: { noDiscovery: true, include: [] } }),
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: '::',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5173,
    host: '::',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
}))
