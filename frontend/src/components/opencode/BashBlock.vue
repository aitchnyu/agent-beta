<script setup lang="ts">
import { computed, ref } from "vue"
import type { ToolBlock } from "../../pages/opencode/types"
import { useScrollBottom } from "../../utils/useScrollBottom"

// A bash call: the command leads the header (with the human `title` as a muted
// subtitle when present), and streaming `output` scrolls to the bottom as it
// grows.
type BashInput = { command?: string }

const props = defineProps<{ block: ToolBlock }>()
const input = computed(() => (props.block.input ?? {}) as BashInput)
const command = computed(() => input.value.command ?? "")

const body = ref<HTMLElement | null>(null)
useScrollBottom(body, () => props.block.output)
</script>

<template>
  <div class="opencode-tool">
    <div class="opencode-tool-head">
      <span class="opencode-tool-name">{{
        command || block.title || block.tool
      }}</span>
      <span v-if="block.status" class="opencode-tool-status">{{
        block.status
      }}</span>
    </div>
    <p
      v-if="command && block.title && block.title !== command"
      class="text-muted small"
    >
      {{ block.title }}
    </p>
    <pre v-if="block.output" ref="body" class="opencode-tool-body">{{
      block.output
    }}</pre>
  </div>
</template>
