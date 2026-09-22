<script setup lang="ts">
// A tiny native-<details> dropdown. Owns the open/close mechanics —
// outside click, Escape, and entry clicks — so consumers are markup-only:
// a ``trigger`` slot for the summary, the default slot for the entries
// (links/buttons carrying .layout-menu-link). Positioning is plain CSS
// (absolute panel anchored to the trigger's side via ``align``); no
// Popper — every deployment site anchors to a top edge and drops into
// open space.
import { onBeforeUnmount, onMounted, ref } from "vue"

// ``caret``: render the summary's ▾ (default) or leave the trigger slot
// as-is — a boxed trigger (e.g. a button-styled span) carries its own
// caret INSIDE the box, where the ::after one would sit detached outside.
withDefaults(defineProps<{ align?: "left" | "right"; caret?: boolean }>(), {
  align: "left",
  caret: true,
})

const root = ref<HTMLDetailsElement>()

function close(): void {
  if (root.value) root.value.open = false
}

function onDocClick(e: MouseEvent): void {
  const el = root.value
  if (el?.open && !el.contains(e.target as Node)) close()
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape") close()
}

function onPanelClick(): void {
  // Any entry click closes: entries are links/buttons that navigate or
  // act, and the panel must not survive either.
  close()
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
  <details
    ref="root"
    class="layout-dropdown"
    :class="
      align === 'right' ? 'layout-dropdown-right' : 'layout-dropdown-left'
    "
  >
    <summary
      class="layout-menu-summary"
      :class="{ 'layout-menu-no-caret': !caret }"
    >
      <slot name="trigger" />
    </summary>
    <div class="layout-menu-panel" @click="onPanelClick">
      <slot />
    </div>
  </details>
</template>
