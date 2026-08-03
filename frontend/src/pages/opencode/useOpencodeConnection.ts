import { computed, onUnmounted, ref } from "vue"
import axios from "axios"
import { OpencodeEventSchema } from "../../schemas"
import type { OpencodeEvent } from "../../schemas"
import {
  postAbort,
  postDeleteSession,
  postPermission as apiPostPermission,
} from "./api"
import { parseSsePayloads } from "./parseSse"
import type { PermissionReply } from "./types"
import { showErrorToast } from "../../utils/sweetalert"

// localStorage key for the active opencode session id. Persisted across
// refreshes so a mid-turn reload reuses the session instead of orphaning it
// (opencode would keep the old session running unattended).
const SESSION_KEY = "opencode.session_id"

function _loadStoredSession(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY)
  } catch {
    return null
  }
}

function _storeSession(id: string | null) {
  try {
    if (id) localStorage.setItem(SESSION_KEY, id)
    else localStorage.removeItem(SESSION_KEY)
  } catch {
    // Ignore — storage may be unavailable (privacy mode); the session just
    // won't survive a refresh.
  }
}

// Hooks the consumer (the facade → transcript) wires into `send` so the
// transport is decoupled from the transcript: every parsed event is routed via
// `onEvent`, and the turn's start/end are signalled so the transcript can
// snapshot per-turn state and freeze/notify on completion. Param names are `_`
// because the project's base no-unused-vars flags type-position params; the
// param *type* is the documentation.
export type TurnHooks = {
  onEvent(_: OpencodeEvent): void
  onTurnStart(): void
  onTurnEnd(_: { clean: boolean; userStopped: boolean }): void
}

// The opencode transport: owns the session id + the SSE stream + the HTTP
// actions (stop / reset / answer-permission). It knows nothing about the
// transcript — parsed events and turn lifecycle are handed to injected hooks.
// State flips happen only after the server confirms; a failed action surfaces a
// toast and leaves prior state intact.
export function useOpencodeConnection() {
  const sessionId = ref<string | null>(_loadStoredSession())
  const isStreaming = ref(false)
  // True while a Reset-session round-trip (abort + daemon delete) is in flight,
  // so the button can disable and re-entry is blocked.
  const resetting = ref(false)
  const hasSession = computed(() => sessionId.value !== null)
  // Live count of SSE events received in this conversation window (resets on
  // clear) + an opt-in, machine-readable event log for debugging. Both are
  // per-raw-frame, so they live with the transport (pre-parse).
  const eventCount = ref(0)
  const isInDebugMode = ref(false)
  const debugLogs = ref<string[]>([])
  // Plain `let` (no reactivity needed; never read in a template/computed).
  let controller: AbortController | null = null
  // Lifecycle flag so events arriving after unmount (the fetch is still
  // resolving) don't fire hooks on a dead composable.
  let isAlive = true
  // Set by stop() so the consumer can tell a natural finish from a user stop
  // (signalled via onTurnEnd). Reset at the start of send().
  let userStopped = false

  async function send(message: string, hooks: TurnHooks) {
    const text = message.trim()
    if (!text || isStreaming.value) return
    isStreaming.value = true
    controller = new AbortController()
    userStopped = false
    hooks.onTurnStart()
    let cleanEnd = false
    try {
      const resp = await axios.post(
        "/api/opencode/prompt/",
        { message: text, session_id: sessionId.value },
        {
          adapter: "fetch",
          responseType: "stream",
          signal: controller.signal,
        },
      )
      const body = resp.data as ReadableStream<Uint8Array> | null
      if (!body) throw new Error("agent returned no stream")
      for await (const payload of parseSsePayloads(body)) {
        if (!isAlive) return
        eventCount.value++
        if (isInDebugMode.value) {
          // Machine-readable dump of the raw frame, capped so a long debug
          // session can't grow the buffer without bound.
          debugLogs.value.push(JSON.stringify(payload, null, 2))
          if (debugLogs.value.length > 1000) debugLogs.value.shift()
        }
        const parsed = OpencodeEventSchema.safeParse(payload)
        if (!parsed.success) continue
        const event = parsed.data
        // The transport owns the session id; the transcript ignores `session`.
        if (event.type === "session") {
          sessionId.value = event.properties.session_id
          _storeSession(event.properties.session_id)
        }
        hooks.onEvent(event)
      }
      cleanEnd = true
    } catch (err: unknown) {
      // A user-initiated stop is not an error to surface.
      if (err instanceof DOMException && err.name === "AbortError") return
      showErrorToast(err, "agent stream failed")
      // The stream failed (daemon down/restart, network drop) — the persisted
      // session id is likely stale, so drop it and let the next prompt create a
      // fresh session instead of erroring until the user hits Clear.
      sessionId.value = null
      _storeSession(null)
    } finally {
      isStreaming.value = false
      hooks.onTurnEnd({ clean: cleanEnd, userStopped })
    }
  }

  async function stop() {
    // Rely on the server-side abort: POST /abort/ tells opencode to stop the
    // turn cleanly, the daemon emits idle, and Django closes the stream. The
    // fetch resolves naturally — no need for a parallel client-side abort
    // (which would race the stream teardown and could mask a daemon failure).
    if (!sessionId.value || !isStreaming.value) return
    userStopped = true
    try {
      await postAbort(sessionId.value)
    } catch (err: unknown) {
      showErrorToast(err, "Failed to stop agent")
    }
  }

  // Best-effort server-side abort of the in-flight turn, for clear/reset. Unlike
  // stop() it doesn't set the user-stop flag (those paths tear down the whole
  // window, so the idle notification is moot). Fire-and-forget; errors swallowed.
  async function abortTurn() {
    if (sessionId.value && isStreaming.value) {
      await postAbort(sessionId.value).catch(() => {})
    }
  }

  // Client-side stream teardown only (no /abort/). Correct for clear/reset
  // (which follow up with abortTurn/deleteSession) and for unmount (we're
  // leaving — there's no /abort/ to call).
  function abortStream() {
    controller?.abort()
  }

  async function deleteSession() {
    if (!sessionId.value) return
    await postDeleteSession(sessionId.value)
  }

  async function postPermission(id: string, reply: PermissionReply) {
    if (!sessionId.value) return
    await apiPostPermission(sessionId.value, id, reply)
  }

  // Clear button: abort the in-flight turn (best-effort) + the stream + the
  // event/debug counters, KEEPING the session id (the next prompt continues it).
  function clearWindow() {
    void abortTurn()
    abortStream()
    eventCount.value = 0
    debugLogs.value = []
  }

  // Reset button (after the daemon delete resolves): drop the session id + clear
  // the counters. The transcript wipe is the page's half of the reset.
  function resetLocal() {
    sessionId.value = null
    _storeSession(null)
    eventCount.value = 0
    debugLogs.value = []
  }

  function toggleDebug() {
    isInDebugMode.value = !isInDebugMode.value
  }

  onUnmounted(() => {
    isAlive = false
    controller?.abort()
  })

  return {
    sessionId,
    streaming: isStreaming,
    resetting,
    hasSession,
    eventCount,
    debugMode: isInDebugMode,
    debugLog: debugLogs,
    send,
    stop,
    abortTurn,
    abortStream,
    deleteSession,
    postPermission,
    clearWindow,
    resetLocal,
    toggleDebug,
  }
}
