<script setup lang="ts">
import { computed } from "vue"

// LucideIcon — an svg file from src/icons (lucide) rendered as a
// currentColor SHAPE: the file is a CSS mask painted with the surrounding
// text color, so icons follow link/button state colors for free (an <img>
// svg cannot inherit currentColor, and inlining would fork the file).
const props = defineProps<{
  src: string
}>()

// Quoted url() + percent-escaped quotes: Vite's inlined svg keeps raw '
// characters (its minifier flips attribute quotes), which terminate a
// single-quoted url() string and silently blank the mask.
const maskValue = computed(() => `url('${props.src.replaceAll("'", "%27")}')`)
</script>

<template>
  <span
    class="lucide-icon"
    :style="{ '--lucide-src': maskValue }"
    aria-hidden="true"
  />
</template>
