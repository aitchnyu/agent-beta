<script setup lang="ts">
import { computed } from "vue"
import type { PermissionBlock } from "../../pages/opencode/types"

// Compact inline record of a permission in the transcript: type + subject
// (filepath for write/edit, command for bash) + complete/cancelled/pending.
// The interactive prompt lives in the pinned PermissionPrompt above the input.
const props = defineProps<{ block: PermissionBlock }>()

const subject = computed(() => props.block.filepath || props.block.command)
const stateText = computed(
  () =>
    ({ answered: "complete", cancelled: "cancelled", asked: "pending" })[
      props.block.state
    ] ?? "pending",
)
const stateClass = computed(
  () =>
    ({
      answered: "text-success",
      cancelled: "text-muted",
      asked: "text-warning",
    })[props.block.state] ?? "text-warning",
)
</script>

<template>
  <div class="opencode-permission-inline">
    <span class="opencode-permission-type">{{ block.permission }}</span>
    <code v-if="subject" class="opencode-permission-cmd-inline">{{
      subject
    }}</code>
    <span class="opencode-permission-state" :class="stateClass">
      {{ stateText }}
    </span>
  </div>
</template>
