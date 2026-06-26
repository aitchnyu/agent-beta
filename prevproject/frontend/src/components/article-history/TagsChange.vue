<script setup lang="ts">
import type { ArticleTagItem } from "../../schemas.ts"

defineProps<{ value: ArticleTagItem[] }>()
</script>

<template>
  <span class="article-history-tags">
    <span
      v-for="tag in value"
      :key="tag.name"
      class="article-tag-badge"
      :style="{ backgroundColor: tag.color }"
    >
      {{ tag.name }}
    </span>
  </span>
</template>
