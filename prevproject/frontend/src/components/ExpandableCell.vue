<script setup lang="ts">
import { ref, onMounted } from "vue"

const props = withDefaults(defineProps<{ maxHeight?: string }>(), {
  maxHeight: "3rem",
})

const isExpanded = ref(false)
const isOverflowing = ref(false)
const contentEl = ref<HTMLDivElement | null>(null)

onMounted(() => {
  if (contentEl.value) {
    isOverflowing.value =
      contentEl.value.scrollHeight > contentEl.value.clientHeight
  }
})
</script>

<template>
  <div
    ref="contentEl"
    :style="
      isExpanded ? {} : { maxHeight: props.maxHeight, overflow: 'hidden' }
    "
  >
    <slot />
  </div>
  <button
    v-if="isOverflowing"
    class="text-cell-toggle"
    @click="isExpanded = !isExpanded"
  >
    {{ isExpanded ? "Show less" : "Show more" }}
  </button>
</template>
