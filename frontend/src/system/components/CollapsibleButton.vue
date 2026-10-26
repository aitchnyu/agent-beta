<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue"
import { markEscape } from "./navbar/navbar"

// A native <details>: the summary (label or #summary slot) toggles a
// panel slot. Closes itself on outside click, Escape, and panel clicks;
// emits linkclick so a parent dropdown can collapse too.
const props = defineProps<{
  label?: string
  summaryClass?: string
  panelClass?: string
}>()
const emit = defineEmits<{ linkclick: [] }>()

const root = ref<HTMLDetailsElement>()
function close(): void {
  if (root.value) root.value.open = false
}
function onPanelClick(): void {
  close()
  emit("linkclick")
}
function onDocClick(e: MouseEvent): void {
  if (root.value?.open && !root.value.contains(e.target as Node)) close()
}
function onKeydown(e: KeyboardEvent): void {
  // Innermost-first: close on Escape and mark the event (navbar/navbar)
  // so a parent dropdown stays open for a second hit.
  if (e.key === "Escape" && root.value?.open) {
    close()
    markEscape(e)
  }
}
onMounted(() => {
  document.addEventListener("click", onDocClick)
  document.addEventListener("keydown", onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick)
  document.removeEventListener("keydown", onKeydown)
})
</script>

<template>
  <details ref="root" class="collapsible-button">
    <summary :class="props.summaryClass">
      <slot name="summary">{{ props.label }}</slot>
    </summary>
    <div
      class="collapsible-button-panel"
      :class="props.panelClass"
      @click="onPanelClick"
    >
      <slot />
    </div>
  </details>
</template>
