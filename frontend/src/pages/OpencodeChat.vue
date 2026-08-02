<script setup lang="ts">
import { ref } from "vue"
import Layout from "../components/Layout.vue"
import PermissionCard from "../components/opencode/PermissionCard.vue"
import RenderRawHtml from "../components/RenderRawHtml.vue"
import { useOpencodeChat } from "./opencode/useOpencodeChat"
import { isNotifySupported } from "./opencode/notify"
import { blockKey } from "./opencode/types"

const input = ref("")
const canNotify = isNotifySupported()
const {
  blocks,
  streaming,
  resetting,
  hasSession,
  eventCount,
  debugMode,
  debugLog,
  notifyGranted,
  notifyDenied,
  send,
  stop,
  clear,
  resetSession,
  answerPermission,
  toggleDebug,
  enableNotifications,
} = useOpencodeChat()

async function sendPrompt() {
  const message = input.value.trim()
  if (!message || streaming.value) return
  input.value = ""
  await send(message)
}
</script>

<template>
  <Layout>
    <div class="container opencode-page">
      <h2>Agent</h2>
      <p>
        Describe a change and the agent will edit files under
        <code>ourapp/</code>, run commands, and ask before doing anything
        destructive.
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
        <template v-for="b in blocks" :key="blockKey(b)">
          <div v-if="b.kind === 'user'" class="opencode-user">{{ b.text }}</div>
          <div v-else-if="b.kind === 'reasoning'" class="opencode-reasoning">
            {{ b.text }}
          </div>
          <RenderRawHtml
            v-else-if="b.kind === 'text'"
            :html="b.text"
            markdown
            class-name="opencode-text"
          />
          <div v-else-if="b.kind === 'tool'" class="opencode-tool">
            <div class="opencode-tool-head">
              <span class="opencode-tool-name">{{ b.tool }}</span>
              <span class="opencode-tool-status">{{ b.status }}</span>
            </div>
            <pre v-if="b.input" class="opencode-tool-input">{{ b.input }}</pre>
            <pre v-if="b.output" class="opencode-tool-output">{{
              b.output
            }}</pre>
          </div>
          <PermissionCard
            v-else-if="b.kind === 'permission'"
            :block="b"
            @answer="(reply) => answerPermission(b, reply)"
          />
        </template>
      </div>
      <form class="opencode-input-row" @submit.prevent="sendPrompt">
        <label class="visually-hidden" for="opencode-input"
          >Message agent</label
        >
        <input
          id="opencode-input"
          v-model="input"
          class="form-control opencode-input"
          :placeholder="streaming ? 'Waiting for server…' : 'Message agent…'"
          :disabled="streaming"
        />
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
        <button
          class="btn btn-sm btn-outline-secondary opencode-debug"
          type="button"
          :class="{ active: debugMode }"
          :aria-pressed="debugMode"
          @click="toggleDebug"
        >
          Debug
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
           present in the DOM for debugging (toggle on with the Debug button). -->
      <pre v-if="debugMode" class="opencode-debug-log" aria-hidden="true">{{
        debugLog.join("\n\n")
      }}</pre>
    </div>
  </Layout>
</template>
