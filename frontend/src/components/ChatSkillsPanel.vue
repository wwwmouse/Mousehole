<script setup lang="ts">
import { onMounted, ref } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import { listSkills } from '@/api/endpoints'
import type { SkillInfo } from '@/api/types'
import { errorMessage } from '@/utils/errors'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const skills = ref<SkillInfo[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    skills.value = await listSkills()
    if (!props.modelValue && skills.value.length > 0) {
      emit('update:modelValue', skills.value[0].id)
    }
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function select(skillId: string): void {
  emit('update:modelValue', skillId)
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="side-panel">
    <header class="side-panel__head">
      <h3 class="side-panel__title">Skill</h3>
      <span class="chip chip--muted">{{ skills.length }}</span>
    </header>
    <p class="side-panel__hint">选择本次执行使用的 Skill，决定产出内容。</p>

    <p v-if="loading" class="side-panel__muted">加载中…</p>
    <p v-else-if="error" class="side-panel__error">{{ error }}</p>

    <ul v-else class="skill-list">
      <li v-for="skill in skills" :key="skill.id">
        <button
          type="button"
          class="skill-item"
          :class="{ 'skill-item--active': modelValue === skill.id }"
          @click="select(skill.id)"
        >
          <AppIcon name="sparkles" :size="13" />
          <span class="skill-item__body">
            <span class="skill-item__name">{{ skill.name }}</span>
            <span class="skill-item__desc">{{ skill.description }}</span>
          </span>
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-subtle);
}

.side-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.side-panel__title {
  margin: 0;
  font-size: 12.5px;
  font-weight: 600;
}

.side-panel__hint {
  margin: 0;
  font-size: 11px;
  color: var(--text-faint);
}

.side-panel__muted {
  margin: 0;
  font-size: 11.5px;
  color: var(--text-muted);
}

.side-panel__error {
  margin: 0;
  font-size: 11.5px;
  color: var(--danger);
}

.skill-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.skill-item {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  width: 100%;
  padding: 7px 8px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
}

.skill-item:hover,
.skill-item--active {
  border-color: var(--accent-border);
  background: var(--accent-soft);
  color: var(--text);
}

.skill-item__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.skill-item__name {
  font-size: 12px;
}

.skill-item__desc {
  font-size: 10.5px;
  line-height: 1.4;
  color: var(--text-faint);
}
</style>
