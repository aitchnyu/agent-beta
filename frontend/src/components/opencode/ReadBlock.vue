<script setup lang="ts">
import { computed } from "vue"
import type { ToolBlock } from "../../pages/opencode/types"
import ToolBody from "./ToolBody.vue"

// A read call: show the target filepath (not the raw input JSON) and, when the
// call is ranged, a "lines x–y" hint. The output arrives as "<num>: <code>", so
// it's rendered with deemphasized line-number prefixes.
type ReadInput = { filePath?: string; offset?: number; limit?: number }

const props = defineProps<{ block: ToolBlock }>()
const input = computed(() => (props.block.input ?? {}) as ReadInput)
const filePath = computed(() => input.value.filePath ?? "")
const range = computed(() => {
  const o = input.value.offset
  const l = input.value.limit
  if (typeof o === "number" && typeof l === "number")
    return `lines ${o}–${o + l - 1}`
  if (typeof l === "number") return `first ${l} lines`
  if (typeof o === "number") return `from line ${o}`
  return ""
})
</script>

<template>
  <div class="opencode-tool">
    <div class="opencode-tool-head">
      <span class="opencode-tool-name">Read</span>
      <span class="opencode-tool-path" :title="filePath">{{ filePath }}</span>
      <span v-if="range" class="opencode-tool-range">{{ range }}</span>
      <span v-if="block.status" class="opencode-tool-status">{{
        block.status
      }}</span>
    </div>
    <ToolBody v-if="block.output" :text="block.output" line-numbers />
  </div>
</template>
