<script setup lang="ts">
defineProps<{ value: string | null }>()

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}
</script>

<template>
  <span class="article-history-value">{{
    value ? formatTime(value) : "(none)"
  }}</span>
</template>
