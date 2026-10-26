<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue"
import { Link } from "@inertiajs/vue3"

// A collapsible button: a native <details> whose summary toggles a link
// panel. Owns its disclosure contract — closes on outside click, Escape,
// and link navigation — so parents only supply label, links, and the
// placement classes (they vary between the wide navbar and the compact
// Menu; the caret comes from .layout-menu-summary's ::after, not markup).
const props = defineProps<{
  label: string
  links: { href: string; label: string }[]
  summaryClass?: string
  panelClass?: string
  linkClass?: string
}>()
// A link was clicked (after closing) — lets a parent dropdown (the
// compact Menu) collapse itself too.
const emit = defineEmits<{ linkclick: [] }>()

const root = ref<HTMLDetailsElement>()
function close(): void {
  if (root.value) root.value.open = false
}
function onDocClick(e: MouseEvent): void {
  if (root.value?.open && !root.value.contains(e.target as Node)) close()
}
function onKeydown(e: KeyboardEvent): void {
  // Innermost-first: when this dropdown closed on Escape, stop the event
  // so a parent dropdown (the compact Menu) stays open for a second hit.
  if (e.key === "Escape" && root.value?.open) {
    close()
    e.stopImmediatePropagation()
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
      {{ props.label }}
    </summary>
    <div class="collapsible-button-panel" :class="props.panelClass">
      <Link
        v-for="l in props.links"
        :key="l.href"
        :class="props.linkClass"
        :href="l.href"
        @click="
          () => {
            close()
            emit('linkclick')
          }
        "
        >{{ l.label }}</Link
      >
    </div>
  </details>
</template>
