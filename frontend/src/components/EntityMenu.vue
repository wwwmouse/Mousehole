<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import AppIcon from '@/components/AppIcon.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import Modal from '@/components/Modal.vue'

const props = withDefaults(
  defineProps<{
    name: string
    kind: 'project' | 'task'
    archived: boolean
    busy?: boolean
  }>(),
  { busy: false },
)

const emit = defineEmits<{
  rename: [name: string]
  toggleArchive: []
  remove: []
}>()

const entityLabel = computed(() => (props.kind === 'project' ? '项目' : '任务'))
const renameTitle = computed(() => `重命名${entityLabel.value}`)
const nameLabel = computed(() => `${entityLabel.value}名称`)

const triggerRef = ref<HTMLButtonElement | null>(null)
const menuOpen = ref(false)
const popStyle = ref<{ top: string; left: string }>({ top: '0px', left: '0px' })

const renameOpen = ref(false)
const renameDraft = ref('')
const renameError = ref<string | null>(null)

const removeOpen = ref(false)

const MENU_WIDTH = 180
const MENU_HEIGHT = 132
const GAP = 6

function toggleMenu(): void {
  if (props.busy) return
  if (menuOpen.value) {
    menuOpen.value = false
    return
  }
  const trigger = triggerRef.value
  if (!trigger) return
  const rect = trigger.getBoundingClientRect()
  let left = rect.right - MENU_WIDTH
  left = Math.max(8, Math.min(left, window.innerWidth - MENU_WIDTH - 8))
  let top = rect.bottom + GAP
  if (top + MENU_HEIGHT > window.innerHeight - 8) {
    top = rect.top - GAP - MENU_HEIGHT
    if (top < 8) top = 8
  }
  popStyle.value = { top: `${Math.round(top)}px`, left: `${Math.round(left)}px` }
  menuOpen.value = true
}

function closeMenu(): void {
  menuOpen.value = false
}

function startRename(): void {
  closeMenu()
  renameDraft.value = props.name
  renameError.value = null
  renameOpen.value = true
}

function closeRename(): void {
  renameOpen.value = false
  renameError.value = null
}

function confirmRename(): void {
  const value = renameDraft.value.trim()
  if (!value) {
    renameError.value = `请填写${nameLabel.value}`
    return
  }
  closeRename()
  emit('rename', value)
}

function onToggleArchive(): void {
  closeMenu()
  emit('toggleArchive')
}

function startRemove(): void {
  closeMenu()
  removeOpen.value = true
}

function confirmRemove(): void {
  removeOpen.value = false
  emit('remove')
}

function onDocumentClick(event: MouseEvent): void {
  if (!menuOpen.value) return
  const target = event.target as Node | null
  if (target && triggerRef.value?.contains(target)) return
  closeMenu()
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && menuOpen.value) closeMenu()
}

onMounted(() => {
  window.addEventListener('click', onDocumentClick)
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('click', onDocumentClick)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="entity-menu">
    <button
      ref="triggerRef"
      type="button"
      class="entity-menu__trigger"
      :class="{ 'entity-menu__trigger--active': menuOpen }"
      :disabled="busy"
      aria-haspopup="menu"
      :aria-expanded="menuOpen"
      :aria-label="`${entityLabel}操作`"
      title="更多操作"
      @click.stop.prevent="toggleMenu"
    >
      <AppIcon name="more" :size="16" />
    </button>

    <Teleport to="body">
      <Transition name="entity-menu">
        <div v-if="menuOpen" class="entity-menu__pop" :style="popStyle" role="menu" @click.stop>
          <button type="button" role="menuitem" class="entity-menu__item" @click="startRename">
            <AppIcon name="edit" :size="14" />
            重命名
          </button>
          <button type="button" role="menuitem" class="entity-menu__item" @click="onToggleArchive">
            <AppIcon name="archive" :size="14" />
            {{ archived ? '取消归档' : '归档' }}
          </button>
          <button
            type="button"
            role="menuitem"
            class="entity-menu__item entity-menu__item--danger"
            @click="startRemove"
          >
            <AppIcon name="trash" :size="14" />
            删除
          </button>
        </div>
      </Transition>
    </Teleport>

    <Modal
      :open="renameOpen"
      :title="renameTitle"
      width="460px"
      :dismissible="!busy"
      @close="closeRename"
    >
      <form class="entity-menu__form" @submit.prevent="confirmRename">
        <label class="field">
          <span class="field__label">{{ nameLabel }}</span>
          <input
            v-model="renameDraft"
            class="input"
            type="text"
            maxlength="200"
            :placeholder="name"
            autofocus
          />
        </label>
        <p v-if="renameError" class="form-error">{{ renameError }}</p>
      </form>

      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="busy" @click="closeRename">取消</button>
        <button type="button" class="btn btn--primary" :disabled="busy" @click="confirmRename">确定</button>
      </template>
    </Modal>

    <ConfirmDialog
      :open="removeOpen"
      title="删除确认"
      :message="`确定删除「${name}」吗？此操作不可撤销。`"
      confirm-label="删除"
      danger
      :busy="busy"
      @close="removeOpen = false"
      @confirm="confirmRemove"
    />
  </div>
</template>

<style scoped>
.entity-menu {
  position: relative;
  display: inline-flex;
  flex-shrink: 0;
}

.entity-menu__trigger {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition:
    background 0.13s ease,
    color 0.13s ease,
    border-color 0.13s ease;
}

.entity-menu__trigger:hover,
.entity-menu__trigger--active {
  background: var(--bg-hover);
  border-color: var(--border);
  color: var(--text);
}

.entity-menu__trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.entity-menu__pop {
  position: fixed;
  z-index: 200;
  display: flex;
  flex-direction: column;
  min-width: 180px;
  padding: 4px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  background: var(--bg-raised);
  box-shadow: var(--shadow-lg);
}

.entity-menu__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition:
    background 0.13s ease,
    color 0.13s ease;
}

.entity-menu__item:hover {
  background: var(--bg-hover);
  color: var(--text);
}

.entity-menu__item--danger {
  color: var(--danger);
}

.entity-menu__item--danger:hover {
  background: var(--danger-soft);
  color: var(--danger);
}

.entity-menu__form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-error {
  margin: 0;
  color: var(--danger);
  font-size: 12.5px;
}

.entity-menu-enter-active,
.entity-menu-leave-active {
  transition:
    opacity 0.12s ease,
    transform 0.12s ease;
}

.entity-menu-enter-from,
.entity-menu-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
