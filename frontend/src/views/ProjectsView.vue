<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import EmptyState from '@/components/EmptyState.vue'
import EntityMenu from '@/components/EntityMenu.vue'
import LoadingState from '@/components/LoadingState.vue'
import NewProjectModal from '@/components/NewProjectModal.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { deleteProject, listProjects, updateProject } from '@/api/endpoints'
import type { Project } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/utils/errors'
import { formatRelative } from '@/utils/format'

const app = useAppStore()

const projects = ref<Project[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const search = ref('')
const statusFilter = ref<string>('all')
const newProjectOpen = ref(false)

const filteredProjects = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return projects.value.filter((project) => {
    const matchesStatus = statusFilter.value === 'all' || project.status === statusFilter.value
    const matchesKeyword =
      keyword.length === 0 ||
      project.name.toLowerCase().includes(keyword) ||
      (project.description ?? '').toLowerCase().includes(keyword)
    return matchesStatus && matchesKeyword
  })
})

const hasFilters = computed(() => search.value.trim().length > 0 || statusFilter.value !== 'all')

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    projects.value = await listProjects({ limit: 200 })
  } catch (error) {
    loadError.value = errorMessage(error)
    projects.value = []
  } finally {
    loading.value = false
  }
}

function onCreated(project: Project): void {
  newProjectOpen.value = false
  projects.value = [project, ...projects.value]
}

async function renameProject(project: Project, name: string): Promise<void> {
  try {
    await updateProject(project.id, { name })
    app.notify('success', '项目已重命名')
    await load()
  } catch (error) {
    app.notifyError(error)
  }
}

async function toggleProjectArchive(project: Project): Promise<void> {
  try {
    const next = project.status === 'archived' ? 'active' : 'archived'
    await updateProject(project.id, { status: next })
    app.notify('success', next === 'archived' ? '项目已归档' : '项目已取消归档')
    await load()
  } catch (error) {
    app.notifyError(error)
  }
}

async function removeProject(project: Project): Promise<void> {
  try {
    await deleteProject(project.id)
    app.notify('success', '项目「' + project.name + '」已删除')
    await load()
  } catch (error) {
    app.notifyError(error)
  }
}

onMounted(() => {
  void load()
  void app.loadWorkspace()
})
</script>

<template>
  <div class="projects-page">
    <PageHeader title="Projects" description="长期项目及其资料、任务的组织单元。">
      <template #actions>
        <button type="button" class="btn btn--ghost btn--icon" title="刷新" @click="load">
          <AppIcon name="refresh" :size="16" />
        </button>
        <button type="button" class="btn btn--primary" @click="newProjectOpen = true">
          <AppIcon name="plus" :size="16" />
          新建 Project
        </button>
      </template>
    </PageHeader>

    <div class="toolbar">
      <div class="search-box">
        <AppIcon name="search" :size="15" />
        <input
          v-model="search"
          type="search"
          class="search-box__input"
          placeholder="搜索项目名称或描述…"
          aria-label="搜索项目"
        />
      </div>
      <select v-model="statusFilter" class="select select--compact" aria-label="按状态筛选">
        <option value="all">全部状态</option>
        <option value="active">进行中</option>
        <option value="archived">已归档</option>
      </select>
      <span class="toolbar__count">{{ filteredProjects.length }} / {{ projects.length }} 个项目</span>
    </div>

    <LoadingState v-if="loading" label="正在加载项目…" />

    <div v-else-if="loadError" class="panel panel--error">
      <AppIcon name="alert" :size="16" />
      <div>
        <p class="panel--error__title">项目加载失败</p>
        <p class="panel--error__desc">{{ loadError }}</p>
      </div>
      <button type="button" class="btn btn--ghost btn--sm" @click="load">重试</button>
    </div>

    <EmptyState
      v-else-if="projects.length === 0"
      icon="folder"
      title="还没有 Project"
      description="创建一个 Project，把长期跟进的工作和资料沉淀下来。"
    >
      <button type="button" class="btn btn--primary" @click="newProjectOpen = true">
        <AppIcon name="plus" :size="16" />
        新建 Project
      </button>
    </EmptyState>

    <EmptyState
      v-else-if="filteredProjects.length === 0"
      icon="search"
      title="没有匹配的项目"
      description="尝试调整搜索关键词或状态筛选。"
    />

    <ul v-else class="project-list">
      <li v-for="project in filteredProjects" :key="project.id" class="project-row-item">
        <RouterLink :to="`/projects/${project.id}`" class="project-row">
          <span class="project-row__icon"><AppIcon name="folder" :size="16" /></span>
          <span class="project-row__main">
            <span class="project-card__name">{{ project.name }}</span>
            <span class="project-row__desc">{{ project.description || '暂无描述' }}</span>
          </span>
          <span class="project-row__stats">
            {{ project.task_count }} Tasks · {{ project.file_count }} 文件
          </span>
          <span class="project-row__updated">更新于 {{ formatRelative(project.updated_at) }}</span>
          <StatusBadge :status="project.status" kind="project" />
          <AppIcon name="chevron-right" :size="14" class="project-row__chevron" />
        </RouterLink>
        <EntityMenu
          kind="project"
          :name="project.name"
          :archived="project.status === 'archived'"
          @rename="(name) => renameProject(project, name)"
          @toggle-archive="toggleProjectArchive(project)"
          @remove="removeProject(project)"
        />
      </li>
    </ul>

    <NewProjectModal :open="newProjectOpen" @close="newProjectOpen = false" @created="onCreated" />
  </div>
</template>

<style scoped>
.projects-page {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  width: min(360px, 100%);
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-muted);
}

.search-box:focus-within {
  border-color: var(--accent-border);
}

.search-box__input {
  flex: 1;
  height: 34px;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 13px;
  outline: none;
}

.toolbar__count {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.project-list {
  list-style: none;
  margin: 0;
  padding: 0;
  border-top: 1px solid var(--border);
}

.project-row-item {
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid var(--border);
}

.project-row {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) 160px 118px auto 18px;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
  padding: 16px 4px;
  color: inherit;
  transition: background 0.13s ease;
}

.project-row:hover {
  background: var(--bg-subtle);
}

.project-row__icon {
  display: grid;
  place-items: center;
  color: var(--accent);
}

.project-row__main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.project-card__name {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--text);
}

.project-row__desc {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12.5px;
  color: var(--text-secondary);
}

.project-row__stats {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--text-muted);
  white-space: nowrap;
}

.project-row__updated {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.project-row__chevron {
  color: var(--text-muted);
}

@media (max-width: 900px) {
  .project-row {
    grid-template-columns: 24px minmax(0, 1fr) auto 18px;
  }

  .project-row__stats,
  .project-row__updated {
    display: none;
  }
}

@media (max-width: 760px) {
  .toolbar {
    flex-wrap: wrap;
  }

  .toolbar__count {
    margin-left: 0;
  }
}
</style>
