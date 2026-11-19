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

    <div v-else class="project-grid">
      <RouterLink
        v-for="project in filteredProjects"
        :key="project.id"
        :to="`/projects/${project.id}`"
        class="card project-card"
      >
        <div class="project-card__head">
          <span class="project-card__icon"><AppIcon name="folder" :size="16" /></span>
          <h2 class="project-card__name">{{ project.name }}</h2>
          <StatusBadge :status="project.status" kind="project" />
          <EntityMenu
            kind="project"
            :name="project.name"
            :archived="project.status === 'archived'"
            @rename="(name) => renameProject(project, name)"
            @toggle-archive="toggleProjectArchive(project)"
            @remove="removeProject(project)"
          />
        </div>
        <p class="project-card__desc">
          {{ project.description || '暂无描述' }}
        </p>
        <div class="project-card__footer">
          <span>{{ project.task_count }} 个 Task</span>
          <span class="dot-sep" aria-hidden="true">·</span>
          <span>{{ project.file_count }} 个文件</span>
          <span class="project-card__updated">更新于 {{ formatRelative(project.updated_at) }}</span>
        </div>
      </RouterLink>
    </div>

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
  font-size: 12px;
  color: var(--text-faint);
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.project-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    transform 0.15s ease;
}

.project-card:hover {
  border-color: var(--border-strong);
  background: var(--bg-raised);
  transform: translateY(-1px);
}

.project-card__head {
  display: flex;
  align-items: center;
  gap: 9px;
}

.project-card__icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-muted);
}

.project-card__name {
  flex: 1;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-card__desc {
  margin: 0;
  min-height: 40px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.project-card__footer {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  font-size: 11.5px;
  color: var(--text-faint);
}

.project-card__updated {
  margin-left: auto;
}

.dot-sep {
  color: var(--text-faint);
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
