import { computed, onUnmounted, ref } from "vue"
import axios from "axios"
import { OpencodeEventSchema } from "../../schemas"
import type { OpencodeEvent, Part } from "../../schemas"
import {
  getSessionTranscript,
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
  onTurnEnd(_: {
    clean: boolean
    userStopped: boolean
    recovered?: boolean
    timedOut?: boolean
    cancelled?: boolean
  }): void
}

// True if the most recent tool part is still running (state.status not
// completed/error). A tool flips status to running/pending mid-execution and to
// completed/error when done — without adding a new part — so parts.length alone
// can't see it. Only the LAST tool is checked, so a tool stuck non-terminal in a
// prior turn doesn't pin recovery to the 60s cap (it isn't the active tool).
export function lastToolRunning(parts: Part[]): boolean {
  for (let i = parts.length - 1; i >= 0; i--) {
    const part = parts[i]
    if (part && part.type === "tool") {
      const status = part.state?.status
      return status !== "completed" && status !== "error"
    }
  }
  return false
}

// The opencode transport: owns the session id + the SSE stream + the HTTP
// actions (stop / reset / answer-permission). It knows nothing about the
// transcript — parsed events and turn lifecycle are handed to injected hooks.
// State flips happen only after the server confirms; a failed action surfaces a
// toast and leaves prior state intact.
export function useOpencodeConnection() {
  const sessionId = ref<string | null>(_loadStoredSession())
  const isStreaming = ref(false)
  // True while the transport polls the daemon transcript to recover a turn
  // after the SSE stream dropped (dev-server reload / daemon bounce).
  const recovering = ref(false)
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
  // AbortController for the in-flight recovery poll, so stop/clear/reset/unmount
  // can cancel a hung fetch (e.g. during a dev-server reload) instead of waiting
  // on axios's default (no) timeout.
  let recoveryController: AbortController | null = null
  // Lifecycle flag so events arriving after unmount (the fetch is still
  // resolving) don't fire hooks on a dead composable.
  let isAlive = true
  // Set by stop() so the consumer can tell a natural finish from a user stop
  // (signalled via onTurnEnd). Reset at the start of send().
  let userStopped = false
  // Set by clearWindow()/resetLocal() to break a running _recover loop so a
  // wipe mid-recovery isn't repopulated on the next poll, and threaded into
  // onTurnEnd so a cancelled recovery doesn't fire a "reply recovered" notify.
  // Reset at the start of send() (not _recover) so a clear/reset signalled any
  // time during the turn survives into recovery.
  let recoveryCancelled = false

  // Recovery poll outcomes (see _recover):
  //   "quiet"     — the turn settled (2 quiet polls); reply is complete.
  //   "timeout"   — the 60s cap (or a late poll failure) hit with a partial
  //                 reply; the daemon may still be running.
  //   "error"     — the daemon was never reachable (no parts reconciled).
  //   "cancelled" — stop/clear/reset/unmount broke the loop.
  type RecoveryOutcome = "quiet" | "timeout" | "error" | "cancelled"

  async function send(message: string, hooks: TurnHooks) {
    const text = message.trim()
    if (!text || isStreaming.value) return
    isStreaming.value = true
    controller = new AbortController()
    userStopped = false
    recoveryCancelled = false
    hooks.onTurnStart()
    let cleanEnd = false
    let recovered = false
    let timedOut = false
    try {
      const resp = await axios.post(
        "/agent/api/prompt/",
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
      // A dropped stream (dev-server reload after mergescratch, daemon bounce,
      // network blip): the opencode daemon is a separate process that keeps
      // running the turn and persists it. Poll its transcript and reconcile so
      // the final message still lands instead of being lost.
      if (sessionId.value) {
        const outcome = await _recover(sessionId.value, hooks)
        if (outcome === "cancelled") return
        if (outcome === "quiet") {
          recovered = true
          return
        }
        if (outcome === "timeout") {
          timedOut = true
          return
        }
        // outcome === "error": the daemon was unreachable — fall through to the
        // hard failure (toast + drop the likely-stale session id).
      }
      showErrorToast(err, "agent stream failed")
      sessionId.value = null
      _storeSession(null)
    } finally {
      isStreaming.value = false
      recovering.value = false
      hooks.onTurnEnd({
        clean: cleanEnd,
        userStopped,
        recovered,
        timedOut,
        cancelled: recoveryCancelled,
      })
    }
  }

  // Poll the daemon's persisted transcript and reconcile parts after a dropped
  // stream, until the turn goes quiet, the 60s cap hits, or the user cancels.
  // Each poll is bounded by a client timeout and abortable, so a hung fetch
  // during a dev-server reload can't pin the loop past the cap.
  async function _recover(
    sid: string,
    hooks: TurnHooks,
  ): Promise<RecoveryOutcome> {
    recovering.value = true
    recoveryController = new AbortController()
    let lastCount = -1
    let quietPolls = 0
    let reconciled = false
    const deadline = Date.now() + 60_000
    const isCancelled = () => !isAlive || userStopped || recoveryCancelled
    try {
      while (true) {
        if (isCancelled()) return "cancelled"
        if (Date.now() >= deadline) return reconciled ? "timeout" : "error"
        let parts: Part[]
        try {
          parts = await getSessionTranscript(sid, {
            signal: recoveryController.signal,
            timeoutMs: 10_000,
          })
        } catch {
          // Abort (stop/clear/unmount) beats transport failure: if cancelled
          // the user drove it; otherwise a poll failed after we'd reconciled
          // something (→ partial/timeout) or before (→ error).
          return isCancelled() ? "cancelled" : reconciled ? "timeout" : "error"
        }
        reconciled = true
        if (isCancelled()) return "cancelled"
        for (const part of parts) {
          hooks.onEvent({ type: "message.part.updated", properties: { part } })
        }
        // Quiet = no new parts since the last poll AND the current turn's tool
        // (the last tool part) isn't still running. Two quiet polls means the
        // turn's tail has landed.
        if (parts.length === lastCount && !lastToolRunning(parts)) quietPolls++
        else quietPolls = 0
        lastCount = parts.length
        if (quietPolls >= 2) return "quiet"
        await _sleep(2000)
      }
    } finally {
      recovering.value = false
      recoveryController = null
    }
  }

  function _sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  // On page load, if the restored transcript looks in-flight (a tool still
  // running), keep polling until it settles. Mirrors _recover but is a
  // background catch-up: the page has already applied the one-shot tail via
  // applyParts, so this only fires onEvent hooks — no onTurnStart/onTurnEnd, so
  // no notifications fire on a plain page load.
  async function resume(hooks: TurnHooks): Promise<void> {
    if (!sessionId.value || isStreaming.value || recovering.value) return
    isStreaming.value = true
    userStopped = false
    recoveryCancelled = false
    try {
      await _recover(sessionId.value, hooks)
    } finally {
      isStreaming.value = false
    }
  }

  async function stop() {
    // Rely on the server-side abort: POST /abort/ tells opencode to stop the
    // turn cleanly, the daemon emits idle, and Django closes the stream. The
    // fetch resolves naturally — no need for a parallel client-side abort
    // (which would race the stream teardown and could mask a daemon failure).
    if (!sessionId.value || !isStreaming.value) return
    userStopped = true
    recoveryController?.abort()
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
    recoveryCancelled = true
    recoveryController?.abort()
    void abortTurn()
    abortStream()
    eventCount.value = 0
    debugLogs.value = []
  }

  // Reset button (after the daemon delete resolves): drop the session id + clear
  // the counters. The transcript wipe is the page's half of the reset.
  function resetLocal() {
    recoveryCancelled = true
    recoveryController?.abort()
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
    recoveryController?.abort()
  })

  return {
    sessionId,
    streaming: isStreaming,
    recovering,
    resetting,
    hasSession,
    eventCount,
    debugMode: isInDebugMode,
    debugLog: debugLogs,
    send,
    resume,
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
