<script setup lang="ts">
import type {
  PermissionBlock,
  PermissionReply,
} from "../../pages/opencode/types"
import PermissionCard from "./PermissionCard.vue"

// The pinned, interactive permission prompt shown above the input field. Wraps
// PermissionCard (the buttons + command) and adds a "i / n" queue indicator when
// more than one permission is pending this turn. Only one prompt is shown at a
// time — the parent binds it to the first pending block and advances on answer.
defineProps<{ block: PermissionBlock; index: number; total: number }>()
const emit = defineEmits<{ answer: [reply: PermissionReply] }>()
</script>

<template>
  <div>
    <p v-if="total > 1" class="opencode-permission-queue text-muted small">
      Permission {{ index }} of {{ total }}
    </p>
    <PermissionCard :block="block" @answer="(r) => emit('answer', r)" />
  </div>
</template>
