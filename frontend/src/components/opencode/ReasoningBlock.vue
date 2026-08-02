<script setup lang="ts">
import { ref } from "vue"
import { useScrollBottom } from "../../utils/useScrollBottom"

// Reasoning streams token-by-token into a capped, scrollable box. Pin it to the
// bottom unconditionally (a live tail) so the newest thinking stays in view as
// it arrives — distinct from bash output, which only follows when near the
// bottom so you can scroll up to read it.
const props = defineProps<{ text: string }>()
const body = ref<HTMLElement | null>(null)
useScrollBottom(body, () => props.text, true)
</script>

<template>
  <div ref="body" class="opencode-reasoning">
    {{ text }}
  </div>
</template>
