<script setup lang="ts">
// Generic hide-on-scroll wrapper: sticky, slides fully out of view while
// the user scrolls down and returns on any upward scroll. Content rides
// the default slot; the consumer's fallthrough class carries the visuals
// (e.g. .layout-navbar) while the mechanics live in .hide-on-scroll.
import { onBeforeUnmount, onMounted, ref } from "vue"

// Scrolling DOWN hides the bar while reading; any upward scroll brings it
// straight back. The threshold keeps sub-pixel/jitter scrolls from
// toggling, and the very top of the page always shows it.
const hidden = ref(false)
let lastScrollY = 0
function onScroll(): void {
  const y = window.scrollY
  if (y < 10) hidden.value = false
  else if (y > lastScrollY + 4) hidden.value = true
  else if (y < lastScrollY - 4) hidden.value = false
  lastScrollY = y
}
onMounted(() => window.addEventListener("scroll", onScroll, { passive: true }))
onBeforeUnmount(() => window.removeEventListener("scroll", onScroll))
</script>

<template>
  <div class="hide-on-scroll" :class="{ 'hide-on-scroll-hidden': hidden }">
    <slot />
  </div>
</template>
