<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from "vue"
import Layout from "../components/Layout.vue"
import PageTitle from "../components/PageTitle.vue"
import PermissionPrompt from "../components/opencode/PermissionPrompt.vue"
import PermissionInline from "../components/opencode/PermissionInline.vue"
import ReasoningBlock from "../components/opencode/ReasoningBlock.vue"
import RichTextViewer from "../components/RichTextViewer.vue"
import ToolBlock from "../components/opencode/ToolBlock.vue"
import {
  lastToolRunning,
  useOpencodeConnection,
} from "./opencode/useOpencodeConnection"
import { useOpencodeTranscript } from "./opencode/useOpencodeTranscript"
import { useOpencodeNotifications } from "./opencode/useOpencodeNotifications"
import { getSessionTranscript } from "./opencode/api"
import { blockKey } from "./opencode/types"
import type { PermissionBlock, PermissionReply } from "./opencode/types"
import { showErrorToast } from "../utils/sweetalert"

const input = ref("")
const inputEl = ref<HTMLTextAreaElement | null>(null)

// Auto-grow the textarea with its content (capped), so it stays a single line
// until the message wraps. resize: none in CSS — growth is driven from here.
function autoresize() {
  const el = inputEl.value
  if (!el) return
  el.style.height = "auto"
  el.style.height = Math.min(el.scrollHeight, 200) + "px"
}

// Enter inserts a newline (multi-line editing); Enter on a blank line sends.
// Shift+Enter always inserts a newline. The Send button still submits too.
function onKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter" || event.shiftKey) return
  const el = event.target as HTMLTextAreaElement
  const pos = el.selectionStart
  const lineStart = input.value.lastIndexOf("\n", pos - 1) + 1
  if (input.value.slice(lineStart, pos).trim() === "") {
    event.preventDefault()
    void sendPrompt()
  }
}

// Compose the two layers directly (no facade): the transport owns the stream +
// HTTP + session; the transcript owns the blocks. The actions below cross both
// (send pushes a user block then streams; answer/clear/reset touch HTTP + state).
const conn = useOpencodeConnection()
const transcript = useOpencodeTranscript()

const { streaming, resetting, hasSession, eventCount, debugLog, recovering } =
  conn
const { blocks, activePermission, activePermissionIndex, permissionTotal } =
  transcript

// Page-local liveness flag so a navigate-away between the transcript fetch and
// the reconcile doesn't mutate the transcript post-unmount.
let isPageAlive = true
onUnmounted(() => {
  isPageAlive = false
})

// Restore the recent transcript after a refresh/redeploy cut-off: the daemon
// persisted the session, so pull its tail and reconcile. Best-effort — if the
// daemon is down we leave the window empty. If the restored tail looks in-flight
// (a tool still running), keep polling via resume() so a mid-turn reload catches
// the rest of the reply instead of freezing on a partial.
onMounted(async () => {
  if (!conn.sessionId.value) return
  try {
    const parts = await getSessionTranscript(conn.sessionId.value)
    if (!isPageAlive) return
    const tail = parts.slice(-80)
    transcript.applyParts(tail)
    if (tail.length > 0 && lastToolRunning(tail)) {
      await conn.resume(transcript.turnHooks)
    }
  } catch {
    // daemon unreachable — silently skip
  }
})

async function send(message: string) {
  const text = message.trim()
  if (!text || streaming.value) return
  transcript.pushUser(text)
  await conn.send(text, transcript.turnHooks)
}

async function sendPrompt() {
  const message = input.value.trim()
  if (!message || streaming.value) return
  input.value = ""
  await nextTick()
  autoresize()
  await send(message)
}

// Drop the transcript but KEEP the session id, so the next prompt continues the
// same daemon session. Best-effort abort the in-flight turn first so the wiped
// view isn't repopulated by its deltas.
function clear() {
  conn.clearWindow()
  transcript.clear()
}

// Kill the daemon session entirely and reset the view. Client teardown first so
// the UI stops spinning during the daemon round-trip; abort precedes delete
// (deleting a running session is undefined). Best-effort: a failure still
// resets the client and surfaces a toast.
async function resetSession() {
  if (resetting.value || !conn.sessionId.value) return
  resetting.value = true
  const wasStreaming = streaming.value
  conn.abortStream()
  try {
    if (wasStreaming) await conn.abortTurn()
    await conn.deleteSession()
  } catch (err: unknown) {
    showErrorToast(err, "Failed to reset session")
  } finally {
    conn.resetLocal()
    transcript.clear()
    resetting.value = false
  }
}

// POST the reply (transport), then flip the block state (transcript) only on
// success. `pending` gates double-clicks and is cleared in finally.
async function answerPermission(
  block: PermissionBlock,
  reply: PermissionReply,
) {
  if (!conn.sessionId.value || block.pending || block.state !== "asked") return
  block.pending = true
  try {
    await conn.postPermission(block.id, reply)
    transcript.markAnswered(block, reply)
  } catch (err: unknown) {
    showErrorToast(err, "Failed to answer permission")
  } finally {
    block.pending = false
  }
}

const stop = conn.stop

// OS-notification permission lives in its own module (orthogonal to transport/
// transcript); the browser persists it across refreshes, so it's the source of
// truth.
const { canNotify, notifyGranted, notifyDenied, enableNotifications } =
  useOpencodeNotifications()
</script>

<template>
  <Layout>
    <PageTitle value="Agent" />
    <div class="container opencode-page">
      <h2>Agent</h2>
      <p>
        Describe a change and the agent will edit files under
        <code>ourapp/</code>, run commands, and ask before doing anything
        destructive.
      </p>
      <p v-if="recovering" class="opencode-recovering" role="status">
        Connection dropped — recovering the agent's reply…
      </p>
      <div
        class="opencode-transcript"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
      >
        <p v-if="!blocks.length" class="opencode-empty text-muted">
          Send a message to start.
        </p>
        <template v-for="block in blocks" :key="blockKey(block)">
          <div v-if="block.kind === 'user'" class="opencode-user">
            {{ block.text }}
          </div>
          <ReasoningBlock
            v-else-if="block.kind === 'reasoning'"
            :text="block.text"
          />
          <RichTextViewer
            v-else-if="block.kind === 'text'"
            :html="block.text"
            markdown
            class-name="opencode-text"
          />
          <ToolBlock v-else-if="block.kind === 'tool'" :block="block" />
          <PermissionInline
            v-else-if="block.kind === 'permission'"
            :block="block"
          />
        </template>
      </div>
      <PermissionPrompt
        v-if="activePermission"
        class="opencode-permission-pinned"
        :block="activePermission"
        :index="activePermissionIndex"
        :total="permissionTotal"
        @answer="
          (reply) =>
            activePermission && answerPermission(activePermission, reply)
        "
      />
      <form class="opencode-input-row" @submit.prevent="sendPrompt">
        <label class="visually-hidden" for="opencode-input"
          >Message agent</label
        >
        <textarea
          id="opencode-input"
          ref="inputEl"
          v-model="input"
          class="form-control opencode-input"
          rows="1"
          :placeholder="streaming ? 'Waiting for server…' : 'Message agent…'"
          @input="autoresize"
          @keydown="onKeydown"
        ></textarea>
        <button
          v-if="streaming"
          type="button"
          class="btn btn-danger opencode-stop"
          @click="stop"
        >
          Stop
        </button>
        <button
          v-else
          class="btn btn-primary opencode-send"
          type="submit"
          :disabled="!input.trim()"
        >
          Send
        </button>
      </form>
      <div class="opencode-actions">
        <span class="opencode-event-count text-muted">
          {{ eventCount }} event{{ eventCount === 1 ? "" : "s" }}
        </span>
        <button
          class="btn btn-sm btn-outline-secondary opencode-clear"
          type="button"
          :disabled="!blocks.length"
          @click="clear"
        >
          Clear conversation
        </button>
        <button
          class="btn btn-sm btn-outline-danger opencode-reset"
          type="button"
          :disabled="!hasSession || resetting || streaming"
          @click="resetSession"
        >
          {{ resetting ? "Resetting…" : "Reset session" }}
        </button>
      </div>
      <p
        v-if="canNotify && !notifyGranted"
        class="opencode-notify-warn small"
        :class="notifyDenied ? 'text-warning' : 'text-muted'"
      >
        <template v-if="notifyDenied">
          Notifications are blocked — enable them in your browser site settings.
        </template>
        <template v-else>
          Notifications are not enabled.
          <a href="#" @click.prevent="enableNotifications">Enable</a>
        </template>
      </p>
      <!-- Machine-readable dump of every received event, hidden from the UI but
           present in the DOM for debugging (always on). -->
      <pre class="opencode-debug-log" aria-hidden="true">{{
        debugLog.join("\n\n")
      }}</pre>
    </div>
  </Layout>
</template>
