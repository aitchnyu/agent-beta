<script setup lang="ts">
defineProps<{ value: string }>()
</script>

<template>
  <span class="article-history-value">{{ value }}</span>
</template>
