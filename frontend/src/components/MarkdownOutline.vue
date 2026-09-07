<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue"

const props = defineProps<{
  entries: { level: number; text: string; id: string }[]
}>()

// The outline collapses at 300px; the toggle appears only when the list is
// actually taller (measured post-render — headings wrap unpredictably). The
// entries arrive async (after the markdown renders), so measure on mount AND
// on every entries change, both after the DOM update.
const COLLAPSED_MAX = 300
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
       taller than its 300px cap, a bottom-edge toggle expands/collapses it. -->
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
        :class="`markdown-outline-l${e.level}`"
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
