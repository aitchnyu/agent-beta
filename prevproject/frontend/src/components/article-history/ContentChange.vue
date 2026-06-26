<script setup lang="ts">
import RenderRawHtml from "../RenderRawHtml.vue"

defineProps<{ value: string; isExpanded: boolean }>()
</script>

<template>
  <div
    class="article-history-content-body-wrapper"
    :class="{ 'is-expanded': isExpanded }"
  >
    <RenderRawHtml :html="value" className="article-history-content-body" />
  </div>
</template>
