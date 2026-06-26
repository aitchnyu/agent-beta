<script setup lang="ts">
import type { ArticleUserProfile } from "../../schemas.ts"

defineProps<{ value: ArticleUserProfile }>()
</script>

<template>
  <span class="article-history-author">
    <a
      v-if="value.public_id"
      :href="`/users/id/${value.public_id}`"
      class="article-history-author-link"
      >{{ value.title }}</a
    >
    <span v-else>{{ value.title }}</span>
  </span>
</template>
