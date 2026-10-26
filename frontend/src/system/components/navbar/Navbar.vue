<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  onMounted,
  provide,
  ref,
  useSlots,
} from "vue"
import type { VNode } from "vue"
import { Comment, Fragment } from "vue"
import { Link } from "@inertiajs/vue3"
import HideOnScroll from "../HideOnScroll.vue"
import leafIcon from "../../icons/leaf.svg"
import { isEscapeMarked, navbarCloseMenuKey, navbarCompactKey } from "./navbar"

// The responsive top bar: Home link, an entries slot (flat when wide,
// folded into a "Menu" dropdown when compact), and the #right auth slot.
// Provides placement context + a close-Menu callback for the items.

// Evaluated at setup (not on mount) so narrow devices never render one
// wide-layout frame first.
const navMedia = window.matchMedia("(max-width: 767.98px)")
const navCompact = ref(navMedia.matches)
function onMediaChange(event: MediaQueryListEvent): void {
  navCompact.value = event.matches
}
onMounted(() => navMedia.addEventListener("change", onMediaChange))
onBeforeUnmount(() => navMedia.removeEventListener("change", onMediaChange))
provide(navbarCompactKey, navCompact)

const navMenu = ref<HTMLDetailsElement>()
function closeMenu(): void {
  if (navMenu.value) navMenu.value.open = false
}
provide(navbarCloseMenuKey, closeMenu)

// The compact Menu renders only when entries exist; the slot's own v-if
// gates them, so walk the slot tree for real vnodes.
const slots = useSlots()
const hasItems = computed(() => {
  const walk = (vnodes: VNode[]): boolean =>
    vnodes.some((v) => {
      if (v.type === Comment) return false
      if (v.type === Fragment)
        // Fragment children may be a bare string — count it as content.
        return Array.isArray(v.children)
          ? walk(v.children as VNode[])
          : v.children != null
      return true
    })
  return walk((slots.default?.() ?? []) as VNode[])
})

// The compact Menu is a native <details>: close on outside click and on
// Escape (entries also close it on navigate via navbarCloseMenu).
function onDocClick(e: MouseEvent) {
  if (navMenu.value?.open && !navMenu.value.contains(e.target as Node))
    navMenu.value.open = false
}
function onKeydown(e: KeyboardEvent) {
  // Skip when a nested dropdown consumed this Escape (marked, not
  // stopped — see navbar.ts) so closing stays innermost-first.
  if (e.key === "Escape" && !isEscapeMarked(e)) closeMenu()
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
  <HideOnScroll class="layout-navbar">
    <Link class="nav-link" href="/" aria-label="Home"
      ><img :src="leafIcon" alt="" class="home-leaf-icon" />
    </Link>
    <slot v-if="!navCompact" />
    <details v-else-if="hasItems" ref="navMenu" class="layout-navmenu">
      <summary class="nav-link layout-menu-summary layout-navmenu-summary">
        Menu
      </summary>
      <div class="layout-menu-panel layout-navmenu-list">
        <slot />
      </div>
    </details>
    <slot name="right" />
  </HideOnScroll>
</template>
