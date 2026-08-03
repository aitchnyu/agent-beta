<script setup lang="ts">
import { computed } from "vue"
import type { ToolBlock } from "../../pages/opencode/types"
import DiffBody from "./DiffBody.vue"
import ToolBody from "./ToolBody.vue"

// A write (full-file `content`) renders as plain text; an edit
// (`oldString`/`newString`) renders as a unified diff. The filePath leads the
// title so the target is obvious at a glance.
type WriteInput = {
  filePath?: string
  content?: string
  oldString?: string
  newString?: string
}

const props = defineProps<{ block: ToolBlock }>()
const input = computed(() => (props.block.input ?? {}) as WriteInput)
const filePath = computed(() => input.value.filePath ?? "")
// An edit carries oldString+newString; a write carries content.
const isEdit = computed(
  () =>
    input.value.oldString !== undefined && input.value.newString !== undefined,
)
const label = computed(() => (isEdit.value ? "Edit" : "Write"))
</script>

<template>
  <div class="opencode-tool">
    <div class="opencode-tool-head">
      <span class="opencode-tool-name">{{ label }}</span>
      <span class="opencode-tool-path" :title="filePath">{{ filePath }}</span>
      <span v-if="block.status" class="opencode-tool-status">{{
        block.status
      }}</span>
    </div>
    <ToolBody v-if="!isEdit" :text="input.content ?? ''" />
    <DiffBody
      v-else
      :old="input.oldString ?? ''"
      :new="input.newString ?? ''"
    />
  </div>
</template>
