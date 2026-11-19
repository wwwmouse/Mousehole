<script setup lang="ts">
import AppIcon from '@/components/AppIcon.vue'
</script>

<template>
  <div class="not-found">
    <div class="not-found__code">
      <AppIcon name="alert" :size="22" />
      <span>404</span>
    </div>
    <h1 class="not-found__title">页面不存在</h1>
    <p class="not-found__desc">你访问的地址无效，或对应内容已被删除。</p>
    <div class="not-found__actions">
      <RouterLink to="/" class="btn btn--primary">返回 Home</RouterLink>
      <RouterLink to="/projects" class="btn btn--ghost">查看 Projects</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 52vh;
  text-align: center;
}

.not-found__code {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-raised);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 13px;
}

.not-found__title {
  margin: 6px 0 0;
  font-size: 20px;
  font-weight: 600;
}

.not-found__desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.not-found__actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
</style>
