<script setup lang="ts">
import AppShell from '@/components/AppShell.vue'
import ToastStack from '@/components/ToastStack.vue'
</script>

<template>
  <AppShell>
    <RouterView />
  </AppShell>
  <ToastStack />
</template>
