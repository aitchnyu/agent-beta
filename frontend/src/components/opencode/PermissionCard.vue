<script setup lang="ts">
import { nextTick, ref, watch } from "vue"
import {
  PERMISSION_LABELS,
  type PermissionBlock,
  type PermissionReply,
} from "../../pages/opencode/types"

// Renders one permission request: the tool/command being authorised and the
// allow-once / allow-always / reject buttons (or the recorded answer once
// resolved). The card never calls the network — it emits the chosen reply and
// the parent page performs the POST and flips `block.state` on confirmation.
const props = defineProps<{ block: PermissionBlock }>()
const emit = defineEmits<{ answer: [reply: PermissionReply] }>()

function answer(reply: PermissionReply) {
  emit("answer", reply)
}

// Focus the first action when the prompt (re)opens so keyboard users can answer
// without Tab-ing through the prior transcript.
const actionsEl = ref<HTMLDivElement | null>(null)
watch(
  () => props.block.state,
  (state) => {
    if (state !== "asked") return
    void nextTick(() => {
      actionsEl.value?.querySelector<HTMLButtonElement>("button")?.focus()
    })
  },
)
</script>

<template>
  <div
    class="opencode-permission"
    role="alertdialog"
    :aria-label="`Permission request: ${block.permission}`"
  >
    <div class="opencode-permission-head">
      Permission: <strong>{{ block.permission }}</strong>
    </div>
    <pre v-if="block.command" class="opencode-permission-cmd">{{
      block.command
    }}</pre>
    <div
      v-if="block.state === 'asked'"
      ref="actionsEl"
      class="opencode-permission-actions"
    >
      <button
        class="btn btn-sm btn-success"
        :disabled="block.pending"
        @click="answer('once')"
      >
        Allow once
      </button>
      <button
        class="btn btn-sm btn-outline-success"
        :disabled="block.pending"
        @click="answer('always')"
      >
        Allow always<span v-if="block.always"> ({{ block.always }})</span>
      </button>
      <button
        class="btn btn-sm btn-outline-danger"
        :disabled="block.pending"
        @click="answer('reject')"
      >
        Reject
      </button>
    </div>
    <div
      v-else-if="block.state === 'answered'"
      class="opencode-permission-answered"
    >
      {{ block.answer ? PERMISSION_LABELS[block.answer] : "Answered" }}
    </div>
    <div v-else class="opencode-permission-answered">Cancelled</div>
  </div>
</template>
