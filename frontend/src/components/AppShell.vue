<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import { useAppStore } from '@/stores/app'

interface NavItem {
  label: string
  to: string
  icon: string
}

const navItems: NavItem[] = [
  { label: 'Home', to: '/', icon: 'home' },
  { label: 'Projects', to: '/projects', icon: 'folder' },
  { label: 'Library', to: '/library', icon: 'library' },
  { label: 'Skills', to: '/skills', icon: 'sparkles' },
  { label: 'Settings', to: '/settings', icon: 'settings' },
]

const app = useAppStore()
const route = useRoute()

const pageTitle = computed(() => {
  const title = route.meta.title
  return typeof title === 'string' ? title : 'mousehole'
})

const workspaceLabel = computed(() => {
  if (app.workspaceState === 'loading') return '加载工作空间…'
  if (app.workspaceState === 'error') return '工作空间不可用'
  return app.currentWorkspace?.name ?? '未命名工作空间'
})

const workspaceTitle = computed(() => {
  if (app.workspaceState === 'error') return app.workspaceError ?? '工作空间不可用'
  return workspaceLabel.value
})

function isActive(item: NavItem): boolean {
  if (item.to === '/') return route.path === '/'
  return route.path.startsWith(item.to)
}

onMounted(() => {
  void app.loadWorkspace()
})
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--collapsed': app.sidebarCollapsed }">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <RouterLink to="/" class="brand-link" aria-label="mousehole 首页">
          <svg class="brand-mark" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
            <rect x="2.5" y="2.5" width="19" height="19" rx="6" fill="var(--accent-soft)" stroke="var(--accent-border)" />
            <circle cx="12" cy="13.4" r="3.4" fill="none" stroke="var(--accent)" stroke-width="1.8" />
            <path d="M7.2 8.6c1.5-1.3 3.1-1.9 4.8-1.9s3.3.6 4.8 1.9" fill="none" stroke="var(--accent)" stroke-width="1.4" stroke-linecap="round" />
          </svg>
          <span class="brand-copy">
            <span class="brand-name">mousehole</span>
            <span class="brand-sub">personal workbench</span>
          </span>
        </RouterLink>
        <button
          type="button"
          class="sidebar-collapse"
          :aria-label="app.sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
          :title="app.sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
          @click="app.toggleSidebar()"
        >
          <AppIcon name="panel" :size="16" />
        </button>
      </div>

      <nav class="sidebar-nav" aria-label="主导航">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ 'nav-item--active': isActive(item) }"
          :title="app.sidebarCollapsed ? item.label : undefined"
        >
          <AppIcon class="nav-item__icon" :name="item.icon" :size="17" />
          <span class="nav-item__label">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div class="workspace-chip" :title="workspaceTitle">
          <span class="workspace-chip__dot" :data-state="app.workspaceState" aria-hidden="true" />
          <div class="workspace-chip__body">
            <span class="workspace-chip__label">Workspace</span>
            <span class="workspace-chip__name">{{ workspaceLabel }}</span>
          </div>
        </div>
      </div>
    </aside>

    <div class="app-main">
      <header class="topbar">
        <div class="topbar-left">
          <button
            type="button"
            class="topbar-toggle"
            :aria-label="app.sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
            @click="app.toggleSidebar()"
          >
            <AppIcon name="panel" :size="16" />
          </button>
          <span class="topbar-title">{{ pageTitle }}</span>
        </div>
        <div class="topbar-right">
          <span class="topbar-edition">LOCAL / 1.0</span>
        </div>
      </header>

      <main class="app-content">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg);
}

.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  width: var(--sidebar-width);
  height: 100vh;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  background: var(--bg-subtle);
  transition: width 0.18s ease;
  overflow: hidden;
}

.app-shell--collapsed .sidebar {
  width: var(--sidebar-collapsed-width);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 16px 14px 16px 18px;
  border-bottom: 1px solid var(--border);
  min-height: var(--topbar-height);
}

.brand-link {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  overflow: hidden;
}

.brand-mark {
  flex-shrink: 0;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.brand-name {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.1;
  white-space: nowrap;
  color: var(--text);
}

.brand-sub {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-faint);
  white-space: nowrap;
}

.sidebar-collapse {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
}

.sidebar-collapse:hover {
  background: var(--bg-hover);
  color: var(--text);
}

.app-shell--collapsed .sidebar-brand {
  justify-content: center;
  padding: 14px 8px;
}

.app-shell--collapsed .brand-name,
.app-shell--collapsed .sidebar-collapse {
  display: none;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 10px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 13px;
  letter-spacing: 0.01em;
  white-space: nowrap;
  transition:
    background 0.14s ease,
    color 0.14s ease;
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text);
}

.nav-item--active {
  background: var(--accent-soft);
  color: var(--text);
  box-shadow: inset 2px 0 0 var(--accent);
}

.nav-item__icon {
  flex-shrink: 0;
}

.app-shell--collapsed .nav-item {
  justify-content: center;
  padding: 9px 0;
}

.app-shell--collapsed .nav-item__label {
  display: none;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid var(--border);
}

.workspace-chip {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  min-width: 0;
}

.workspace-chip__dot {
  width: 7px;
  height: 7px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--text-faint);
}

.workspace-chip__dot[data-state='ready'] {
  background: var(--success);
}

.workspace-chip__dot[data-state='error'] {
  background: var(--danger);
}

.workspace-chip__dot[data-state='loading'] {
  background: var(--warning);
}

.workspace-chip__body {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.workspace-chip__label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-faint);
  line-height: 1.4;
}

.workspace-chip__name {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.app-shell--collapsed .sidebar-footer {
  padding: 8px;
}

.app-shell--collapsed .workspace-chip {
  justify-content: center;
  padding: 8px 0;
}

.app-shell--collapsed .workspace-chip__body {
  display: none;
}

.app-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: var(--topbar-height);
  padding: 0 32px;
  border-bottom: 1px solid var(--border);
  background: rgba(29, 25, 22, 0.9);
  backdrop-filter: blur(10px);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.topbar-toggle {
  display: none;
  place-items: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-raised);
  color: var(--text-muted);
  cursor: pointer;
}

.topbar-toggle:hover {
  color: var(--text);
}

.topbar-title {
  font-family: var(--font-display);
  font-size: 21px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.02em;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.topbar-edition {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-faint);
}

.app-content {
  flex: 1;
  width: 100%;
  max-width: 1160px;
  padding: 36px 40px 72px;
  margin: 0 auto;
}

.app-shell--collapsed .topbar-toggle {
  display: grid;
}

@media (max-width: 900px) {
  .app-content {
    padding: 20px 18px 48px;
  }

  .topbar {
    padding: 0 18px;
  }
}
</style>
