import { computed, nextTick, onUnmounted, reactive, ref } from "vue"
import axios from "axios"
import { OpencodeEventSchema } from "../../schemas"
import type { Part, PermissionAsked } from "../../schemas"
import { postAbort, postDeleteSession, postPermission } from "./api"
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

// Pure stream → parsed SSE payloads. Reads the fetch body, frames on `\n\n`
// (normalising CRLF/CR → LF so a proxy that rewrites line endings can't hang
// the spinner), joins multi-`data:` lines, and yields each frame's parsed
// JSON. Malformed frames are skipped. The reader lock is released in `finally`
// (also on an early `break` from the consumer). No Vue/state — the caller owns
// validation + dispatch, so this is unit-testable in isolation.
async function* parseSsePayloads(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<Record<string, unknown>> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  const drain = (): Record<string, unknown>[] => {
    const frames: Record<string, unknown>[] = []
    let idx: number
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const dataLines = frame.split("\n").filter((l) => l.startsWith("data:"))
      if (!dataLines.length) continue
      // SSE may split JSON across several `data:` lines; join them and skip a
      // frame that fails to parse so one bad frame can't kill the stream.
      // Strip exactly one leading space after `data:` (SSE spec; mirrors the
      // backend's `_iter_sse` in opencode.py).
      const payload = dataLines
        .map((l) => l.slice(5).replace(/^ /, ""))
        .join("\n")
      try {
        frames.push(JSON.parse(payload) as Record<string, unknown>)
      } catch {
        continue
      }
    }
    return frames
  }
  try {
    let chunk = await reader.read()
    while (!chunk.done) {
      buffer += decoder
        .decode(chunk.value, { stream: true })
        .replace(/\r\n|\r/g, "\n")
      for (const payload of drain()) yield payload
      chunk = await reader.read()
    }
    // Flush any final multi-byte sequence split across the last chunk boundary
    // — without this, a UTF-8 char split exactly on the boundary is dropped and
    // the containing JSON frame fails to parse.
    buffer += decoder.decode().replace(/\r\n|\r/g, "\n")
    for (const payload of drain()) yield payload
  } finally {
    // Release the reader's lock so the underlying fetch is torn down even when
    // the loop throws (abort, network drop). Without this the connection
    // lingers until GC.
    await reader.cancel().catch(() => {})
  }
}

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
  // A part id -> its kind (text/reasoning) so a delta is routed to the right
  // card even when it arrives before the matching message.part.updated.
  const partKind = reactive<Record<string, "text" | "reasoning">>({})
  // O(1) lookup indexes into `blocks` so a long turn with thousands of deltas
  // doesn't degrade to O(n) per event. The maps hold the same reactive objects
  // as `blocks.value`; they're rebuilt only when the list is reset (`clear`).
  const partIndex = new Map<string, PartBlock>()
  const permissionIndex = new Map<string, PermissionBlock>()

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
      freezePendingCards()
      scrollToBottom()
    }
  }

  async function stop() {
    // Rely on the server-side abort: POST /abort/ tells opencode to stop the
    // turn cleanly, the daemon emits idle, and Django closes the stream. The
    // fetch resolves naturally — no need for a parallel client-side abort
    // (which would race the stream teardown and could mask a daemon failure).
    if (!sessionId.value || !streaming.value) return
    try {
      await postAbort(sessionId.value)
    } catch (e: unknown) {
      showErrorToast(e, "Failed to stop agent")
    }
  }

  // Tear down everything client-side: the in-flight fetch, the streaming flag,
  // the transcript, the lookup indexes, the persisted session id, and the
  // partKind map. Shared by `clear` (drop the view) and `resetSession`
  // (kill + drop) so the two stay in lockstep.
  function resetLocal() {
    controller?.abort()
    streaming.value = false
    blocks.value = []
    partIndex.clear()
    permissionIndex.clear()
    sessionId.value = null
    storeSession(null)
    for (const key of Object.keys(partKind)) delete partKind[key]
  }

  function clear() {
    // Drop the transcript and abandon the session so the next prompt starts a
    // fresh opencode session. Best-effort abort an in-flight turn so the daemon
    // isn't left running. The daemon session is NOT deleted here — the daemon
    // keeps its context; use `resetSession` to free it.
    if (streaming.value && sessionId.value) {
      void postAbort(sessionId.value).catch(() => {})
    }
    resetLocal()
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
      existing.state = "asked"
      delete existing.answer
      existing.pending = false
      return
    }
    blocks.value.push(block)
    permissionIndex.set(block.id, block)
    scrollToBottom()
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

  return {
    blocks,
    streaming,
    resetting,
    hasSession,
    send,
    stop,
    clear,
    resetSession,
    answerPermission,
  }
}
