<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue"

const props = defineProps<{
  entries: { level: number; text: string; id: string }[]
}>()

// Collapsed cap (scrollable within). The toggle shows only if the list is
// taller. Entries arrive async, so re-measure on every change.
const COLLAPSED_MAX = 600
const expandable = ref(false)
const expanded = ref(false)
const listEl = ref<HTMLElement>()

async function measure() {
  await nextTick()
  expandable.value = (listEl.value?.scrollHeight ?? 0) > COLLAPSED_MAX
}

onMounted(measure)
watch(() => props.entries, measure, { flush: "post" })

function toggle() {
  expanded.value = !expanded.value
}
</script>

<template>
  <!-- No visible title — the heading list is the outline. When the list is
        taller than its 600px cap, a bottom toggle expands/collapses it. -->
  <nav
    v-if="props.entries.length"
    class="markdown-outline"
    data-outline
    aria-label="Outline"
  >
    <ul
      ref="listEl"
      class="markdown-outline-list"
      :class="{ 'markdown-outline-collapsed': expandable && !expanded }"
    >
      <li
        v-for="e in props.entries"
        :key="e.id"
        :class="`markdown-outline-level${e.level}`"
      >
        <a :href="`#${e.id}`">{{ e.text }}</a>
      </li>
    </ul>
    <button
      v-if="expandable"
      class="markdown-outline-toggle"
      type="button"
      data-outline-toggle
      :aria-expanded="expanded"
      @click="toggle"
    >
      {{ expanded ? "Show less" : "Show all" }}
    </button>
  </nav>
</template>
