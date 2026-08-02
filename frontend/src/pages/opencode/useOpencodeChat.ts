import { computed, nextTick, onUnmounted, reactive, ref } from "vue"
import axios from "axios"
import { OpencodeEventSchema } from "../../schemas"
import type { Part, PermissionAsked } from "../../schemas"
import { postAbort, postDeleteSession, postPermission } from "./api"
import { notify, notifyPermission, requestNotifyPermission } from "./notify"
import { parseSsePayloads } from "./parseSse"
import { parsePermissionBlock } from "./types"
import type {
  Block,
  PartBlock,
  PermissionBlock,
  PermissionReply,
} from "./types"
import { showErrorToast } from "../../utils/sweetalert"

// localStorage key for the active opencode session id. Persisted across
// refreshes so a mid-turn reload reuses the session instead of orphaning it
// (opencode would keep the old session running unattended).
const SESSION_KEY = "opencode.session_id"

function loadStoredSession(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY)
  } catch {
    return null
  }
}

function storeSession(id: string | null) {
  try {
    if (id) localStorage.setItem(SESSION_KEY, id)
    else localStorage.removeItem(SESSION_KEY)
  } catch {
    // Ignore — storage may be unavailable (privacy mode); the session just
    // won't survive a refresh.
  }
}

// parseSsePayloads is imported from ./parseSse (extracted for testing — fixes point 8).

// The opencode chat engine: owns the transcript + session, drives the SSE
// stream from /api/opencode/prompt/, and exposes the user actions (answer a
// permission, stop). State flips happen only after the server confirms — there
// is no optimistic UI, so a failed action leaves the card in its prior state
// and surfaces a toast. The page consumes this and renders; it owns nothing
// but the input box.
export function useOpencodeChat() {
  const blocks = ref<Block[]>([])
  const sessionId = ref<string | null>(loadStoredSession())
  const streaming = ref(false)
  // True while a Reset-session round-trip (abort + daemon delete) is in flight,
  // so the button can disable and re-entry is blocked.
  const resetting = ref(false)
  const hasSession = computed(() => sessionId.value !== null)
  // Plain `let` (no reactivity needed; never read in a template/computed).
  let controller: AbortController | null = null
  // Lifecycle flag so events arriving after unmount (the fetch is still
  // resolving) don't mutate state on a dead composable.
  let isAlive = true
  // Set by stop() so the idle notification doesn't fire on a user-initiated
  // stop: the server closes the stream, so the loop ends "cleanly" and cleanEnd
  // alone can't tell a natural finish from a stop. Reset at the start of send().
  let userStopped = false
  // A part id -> its kind (text/reasoning) so a delta is routed to the right
  // card even when it arrives before the matching message.part.updated.
  const partKind = reactive<Record<string, "text" | "reasoning">>({})
  // O(1) lookup indexes into `blocks` so a long turn with thousands of deltas
  // doesn't degrade to O(n) per event. The maps hold the same reactive objects
  // as `blocks.value`; they're rebuilt only when the list is reset (`clear`).
  const partIndex = new Map<string, PartBlock>()
  const permissionIndex = new Map<string, PermissionBlock>()
  // Live count of SSE events received in this conversation window (resets on
  // clear) + an opt-in, machine-readable event log for debugging.
  const eventCount = ref(0)
  const debugMode = ref(false)
  const debugLog = ref<string[]>([])
  // Whether the browser granted (or denied) notification permission. The
  // browser persists this across refreshes, so it's the source of truth — no
  // separate preference is stored. Snapshotted at load (Notification.permission
  // isn't reactive) and refreshed by enableNotifications().
  const notifyGranted = ref(notifyPermission() === "granted")
  const notifyDenied = ref(notifyPermission() === "denied")

  function scrollToBottom() {
    void nextTick(() => {
      window.scrollTo({
        top: document.documentElement.scrollHeight,
        behavior: "smooth",
      })
    })
  }

  // Freeze any pending cards when the stream ends without resolving them —
  // the user clicked Stop or the daemon dropped, so an unanswered permission
  // must not stay interactive (clicking would POST to a stale id).
  function freezePendingCards() {
    for (const b of blocks.value) {
      if (b.kind === "permission" && b.state === "asked") b.state = "cancelled"
    }
  }

  // True if any permission card is still awaiting an answer — used to suppress
  // the "turn ended" notification (a pending permission means the agent is
  // blocked on you, not idle; that case is covered by the prompt notification).
  function hasAskedPermission(): boolean {
    for (const b of blocks.value) {
      if (b.kind === "permission" && b.state === "asked") return true
    }
    return false
  }

  // Drop partKind entries no longer referenced by a live block so a long
  // multi-turn session doesn't accumulate stale ids forever.
  function prunePartKind() {
    const live = new Set<string>()
    for (const b of blocks.value) {
      if (b.kind === "text" || b.kind === "reasoning" || b.kind === "tool") {
        live.add(b.partID)
      }
    }
    for (const key of Object.keys(partKind)) {
      if (!live.has(key)) delete partKind[key]
    }
  }

  // ---- stream lifecycle ----

  async function send(message: string) {
    const text = message.trim()
    if (!text || streaming.value) return
    blocks.value.push({ kind: "user", uid: crypto.randomUUID(), text })
    prunePartKind()
    streaming.value = true
    controller = new AbortController()
    userStopped = false
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
      for await (const payload of parseSsePayloads(body)) handleEvent(payload)
      cleanEnd = true
    } catch (e: unknown) {
      // A user-initiated stop is not an error to surface.
      if (e instanceof DOMException && e.name === "AbortError") return
      showErrorToast(e, "agent stream failed")
      // The stream failed (daemon down/restart, network drop) — the persisted
      // session id is likely stale, so drop it and let the next prompt create a
      // fresh session instead of erroring until the user hits Clear.
      sessionId.value = null
      storeSession(null)
    } finally {
      streaming.value = false
      // Snapshot asked-state BEFORE freezePendingCards converts asked→cancelled,
      // so a turn that ends with a permission still pending suppresses the
      // "finished" notification (the agent is blocked on you, not idle).
      const hadPending = hasAskedPermission()
      freezePendingCards()
      scrollToBottom()
      // Idle notification: only on a natural turn end (not a user Stop, not a
      // failure), and only if nothing was awaiting an answer — a pending
      // permission means the agent isn't idle, it's blocked on you (covered by
      // the permission notification in pushPermission).
      if (cleanEnd && !userStopped && !hadPending) {
        notify("Agent finished", "Awaiting your reply")
      }
    }
  }

  async function stop() {
    // Rely on the server-side abort: POST /abort/ tells opencode to stop the
    // turn cleanly, the daemon emits idle, and Django closes the stream. The
    // fetch resolves naturally — no need for a parallel client-side abort
    // (which would race the stream teardown and could mask a daemon failure).
    if (!sessionId.value || !streaming.value) return
    userStopped = true
    try {
      await postAbort(sessionId.value)
    } catch (e: unknown) {
      showErrorToast(e, "Failed to stop agent")
    }
  }

  // Tear down the client view: the in-flight fetch, the streaming flag, the
  // transcript, the lookup indexes, and the partKind map. Does NOT touch the
  // session — `clear` calls this directly to wipe only the window while keeping
  // the daemon session for continuity; `resetSession` layers the session-id drop
  // on top via `resetLocal` (after killing the daemon session).
  function clearView() {
    controller?.abort()
    streaming.value = false
    blocks.value = []
    partIndex.clear()
    permissionIndex.clear()
    for (const key of Object.keys(partKind)) delete partKind[key]
    eventCount.value = 0
    debugLog.value = []
  }

  // `clearView` + drop the persisted session id. Used only by `resetSession`,
  // which first frees the daemon session; that keeps the two buttons distinct.
  function resetLocal() {
    clearView()
    sessionId.value = null
    storeSession(null)
  }

  function clear() {
    // Drop the transcript but KEEP the session id, so the next prompt continues
    // the same daemon session — the agent keeps its memory; only the window is
    // wiped. Best-effort abort an in-flight turn first so the cleared view isn't
    // repopulated by its deltas (the daemon session stays). To free the daemon
    // session entirely, use `resetSession`.
    if (streaming.value && sessionId.value) {
      void postAbort(sessionId.value).catch(() => {})
    }
    clearView()
  }

  async function resetSession() {
    // Kill the daemon session entirely (frees its history/context) and reset
    // the view. Re-entry is blocked while a reset is in flight.
    if (resetting.value || !sessionId.value) return
    resetting.value = true
    const sid = sessionId.value
    const wasStreaming = streaming.value
    // Tear down the client stream first so the UI stops spinning while the
    // daemon round-trip runs. `send`'s finally sets streaming=false and freezes
    // pending cards on this abort (AbortError is not surfaced as a toast).
    controller?.abort()
    try {
      // Abort the turn before deleting it (deleting a running session is
      // undefined). Both calls are best-effort: a daemon-down failure still
      // resets the client — the session is effectively gone from the user's
      // view — and surfaces a toast so the failure isn't silent.
      if (wasStreaming) await postAbort(sid).catch(() => {})
      await postDeleteSession(sid)
    } catch (e: unknown) {
      showErrorToast(e, "Failed to reset session")
    } finally {
      resetLocal()
      resetting.value = false
    }
  }

  onUnmounted(() => {
    isAlive = false
    // Tearing down the fetch on navigation is the only place a client-side
    // abort is correct — there's no /abort/ to call because we're leaving.
    controller?.abort()
  })

  function handleEvent(raw: unknown) {
    if (!isAlive) return
    eventCount.value++
    if (debugMode.value) {
      // Machine-readable dump of the raw frame, one per block, newline-joined.
      // Capped so a long debug session can't grow the buffer without bound.
      debugLog.value.push(JSON.stringify(raw, null, 2))
      if (debugLog.value.length > 1000) debugLog.value.shift()
    }
    const parsed = OpencodeEventSchema.safeParse(raw)
    if (!parsed.success) return
    const e = parsed.data
    switch (e.type) {
      case "session":
        sessionId.value = e.properties.session_id
        storeSession(e.properties.session_id)
        break
      case "message.part.delta":
        appendDelta(e.properties.partID, e.properties.delta)
        break
      case "message.part.updated":
        upsertPart(e.properties.part)
        break
      case "permission.asked":
        pushPermission(e.properties)
        break
      case "permission.replied":
        markReplied(e.properties.requestID, e.properties.reply)
        break
      case "error":
        showErrorToast(e.properties.message, "agent error")
        break
      case "session.status":
        break
    }
  }

  // ---- transcript mutators (driven by SSE) ----

  function appendDelta(partID: string, delta: string) {
    if (!delta) return
    const kind = partKind[partID] ?? "text"
    const existing = partIndex.get(partID)
    // Deltas don't apply to tool blocks — a delta for a partID already realised
    // as a tool would otherwise push a stray text block sharing the same key
    // (v-for collision). The tool's full state arrives via message.part.updated.
    if (existing && existing.kind === "tool") return
    if (
      existing &&
      (existing.kind === "text" || existing.kind === "reasoning")
    ) {
      existing.text += delta
      scrollToBottom()
      return
    }
    const block =
      kind === "reasoning"
        ? { kind: "reasoning" as const, partID, text: delta }
        : { kind: "text" as const, partID, text: delta }
    blocks.value.push(block)
    partIndex.set(partID, block)
    scrollToBottom()
  }

  function upsertPart(part: Part) {
    const partID = part.id
    const type = part.type
    if (type === "text" || type === "reasoning") {
      partKind[partID] = type
      const existing = partIndex.get(partID)
      if (
        existing &&
        (existing.kind === "text" || existing.kind === "reasoning")
      ) {
        // Adopt the snapshot's text only when non-empty — the schema doesn't
        // require `text`, so an empty/missing value would otherwise clobber the
        // text a stream of deltas has already accumulated.
        if (part.text) existing.text = part.text
        // A delta may have arrived before this part.updated and created the
        // block with the wrong kind (e.g. reasoning rendered as text). Fix it
        // so subsequent deltas route to the correct card.
        if (existing.kind !== type) existing.kind = type
      } else {
        const block = { kind: type, partID, text: part.text ?? "" }
        blocks.value.push(block)
        partIndex.set(partID, block)
        // The answer begins: reasoning traces are done, follow along.
        if (type === "text") scrollToBottom()
      }
      return
    }
    if (type === "tool") {
      const state = part.state ?? {}
      const existing = partIndex.get(partID)
      const fields = {
        tool: part.tool ?? "",
        status: state.status ?? "",
        input: JSON.stringify(state.input ?? {}, null, 2),
        output:
          typeof state.output === "string"
            ? state.output
            : JSON.stringify(state.output ?? "", null, 2),
      }
      if (existing && existing.kind === "tool") {
        Object.assign(existing, fields)
      } else {
        const block = { kind: "tool" as const, partID, ...fields }
        blocks.value.push(block)
        partIndex.set(partID, block)
        scrollToBottom()
      }
    }
    // step-start / step-finish arrive as their own parts but aren't rendered.
  }

  function pushPermission(p: PermissionAsked) {
    const block = parsePermissionBlock(p)
    const existing = permissionIndex.get(block.id)
    if (existing) {
      // opencode re-emits permission.asked (e.g. on a tool retry after reject).
      // Refresh the metadata AND reopen the card: reset state to "asked" so the
      // action buttons come back and a later permission.replied isn't dropped
      // by the `state === "asked"` gate. Clear any stale answer/pending.
      existing.permission = block.permission
      existing.command = block.command
      existing.always = block.always
      const wasAsked = existing.state === "asked"
      existing.state = "asked"
      delete existing.answer
      existing.pending = false
      if (!wasAsked) {
        notify("Agent needs approval", existing.command || existing.permission)
      }
      return
    }
    blocks.value.push(block)
    permissionIndex.set(block.id, block)
    scrollToBottom()
    notify("Agent needs approval", block.command || block.permission)
  }

  function markReplied(requestID: string, reply: PermissionReply) {
    const b = findPermission(requestID)
    if (!b) {
      // Observable failure: opencode replied for an id we don't know (the
      // id↔requestID contract diverged, or the block was cleared).
      console.warn(
        "[opencode] permission.replied for unknown requestID:",
        requestID,
      )
      return
    }
    // Record the requestID so a later reply carrying it still resolves even if
    // it differs from the block's `id`.
    b.requestId = requestID
    if (b.state === "asked") {
      b.state = "answered"
      b.answer = reply
    }
  }

  // ---- user actions (state set only on confirmed success) ----

  async function answerPermission(
    block: PermissionBlock,
    reply: PermissionReply,
  ) {
    if (!sessionId.value || block.pending || block.state !== "asked") return
    block.pending = true
    try {
      await postPermission(sessionId.value, block.id, reply)
      block.state = "answered"
      block.answer = reply
    } catch (e: unknown) {
      showErrorToast(e, "Failed to answer permission")
    } finally {
      block.pending = false
    }
  }

  function findPermission(id: string): PermissionBlock | undefined {
    const b = permissionIndex.get(id)
    if (b) return b
    // Fall back to requestId: a replied event may carry a requestID that wasn't
    // the block's `id` (the id↔requestID contract is verified by an integration
    // test, but this keeps a divergence from silently losing the user's answer).
    for (const block of permissionIndex.values()) {
      if (block.requestId === id) return block
    }
    return undefined
  }

  function toggleDebug() {
    debugMode.value = !debugMode.value
  }

  // One-way enable (not a toggle): requests OS permission. The warning at the
  // bottom of the page is the only entry point. The browser persists the result
  // across refreshes, so granted stays granted.
  async function enableNotifications() {
    if (notifyGranted.value) return
    // Re-request only from "default" — a denied prompt can't be re-asked
    // programmatically, so the user must change it in browser site settings
    // (the warning reflects that via the denied state).
    const result =
      notifyPermission() === "default"
        ? await requestNotifyPermission()
        : notifyPermission()
    notifyGranted.value = result === "granted"
    notifyDenied.value = result === "denied"
  }

  return {
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
  }
}
