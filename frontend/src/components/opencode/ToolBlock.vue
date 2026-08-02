<script setup lang="ts">
import { computed } from "vue"
import type { ToolBlock } from "../../pages/opencode/types"
import WriteBlock from "./WriteBlock.vue"
import BashBlock from "./BashBlock.vue"

// Thin dispatcher: branches on the tool name and delegates to a focused child.
// The page stays a flat <ToolBlock :block="b" />; each tool gets its own
// component. Unknown tools fall back to a generic name + stringified view.
const props = defineProps<{ block: ToolBlock }>()
const inputText = computed(() => {
  const input = props.block.input
  // `{}` (the default for no input) is truthy but carries nothing — gate on key
  // count so unknown tools without input don't render a noisy `{}` block.
  if (!input || typeof input !== "object") return ""
  return Object.keys(input).length ? JSON.stringify(input, null, 2) : ""
})
</script>

<template>
  <WriteBlock
    v-if="block.tool === 'write' || block.tool === 'edit'"
    :block="block"
  />
  <BashBlock v-else-if="block.tool === 'bash'" :block="block" />
  <div v-else class="opencode-tool">
    <div class="opencode-tool-head">
      <span class="opencode-tool-name">{{ block.title || block.tool }}</span>
      <span v-if="block.status" class="opencode-tool-status">{{
        block.status
      }}</span>
    </div>
    <pre v-if="inputText" class="opencode-tool-body">{{ inputText }}</pre>
    <pre v-if="block.output" class="opencode-tool-body">{{ block.output }}</pre>
  </div>
</template>
