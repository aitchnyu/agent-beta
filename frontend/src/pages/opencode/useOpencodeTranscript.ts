import { computed, nextTick, reactive, ref } from "vue"
import type { OpencodeEvent, Part, PermissionAsked } from "../../schemas"
import { notify } from "./notify"
import type { TurnHooks } from "./useOpencodeConnection"
import { parsePermissionBlock } from "./types"
import type {
  Block,
  PartBlock,
  PermissionBlock,
  PermissionReply,
} from "./types"
import { showErrorToast } from "../../utils/sweetalert"

// The opencode transcript view-model: owns the blocks list + its lookup indexes
// and routes parsed events to the right card. It does no HTTP — events arrive
// via the `turnHooks` bundle (fed by the transport), and user actions that need
// the network are orchestrated by the page (which calls `markAnswered` after the
// POST succeeds). Notifications for permission prompts / idle are fired here.
// Functions not exposed in the return are `_`-prefixed (private helpers).
export function useOpencodeTranscript() {
  const blocks = ref<Block[]>([])
  // A part id -> its kind (text/reasoning) so a delta is routed to the right
  // card even when it arrives before the matching message.part.updated.
  const partKind = reactive<Record<string, "text" | "reasoning">>({})
  // O(1) lookup indexes into `blocks` so a long turn with thousands of deltas
  // doesn't degrade to O(n) per event. The maps hold the same reactive objects
  // as `blocks.value`; they're rebuilt only when the list is reset (`clear`).
  const partIndex = new Map<string, PartBlock>()
  const permissionIndex = new Map<string, PermissionBlock>()
  // Count of permission blocks carried over from PRIOR turns at the moment this
  // turn started. The i/n queue indicator is per-turn, so the index/total
  // subtract this count to avoid a lone prompt reading "3 of 3" in a multi-turn
  // session. Snapshotted in onTurnStart().
  let turnPermissionCount = 0

  // Pinned-permission queue: the first still-asked block is the active prompt
  // (shown above the input). The i/n indicator is PER-TURN: index/total subtract
  // turnPermissionCount so a lone prompt in a multi-turn session doesn't read
  // "3 of 3".
  const permissionBlocks = computed(() =>
    blocks.value.filter((b): b is PermissionBlock => b.kind === "permission"),
  )
  const activePermission = computed(
    () => permissionBlocks.value.find((b) => b.state === "asked") ?? null,
  )
  const activePermissionIndex = computed(() => {
    const active = activePermission.value
    return active
      ? permissionBlocks.value.indexOf(active) + 1 - turnPermissionCount
      : 1
  })
  const permissionTotal = computed(
    () => permissionBlocks.value.length - turnPermissionCount,
  )

  function _scrollToBottom() {
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
  function _freezePendingCards() {
    for (const block of blocks.value) {
      if (block.kind === "permission" && block.state === "asked")
        block.state = "cancelled"
    }
  }

  // True if any permission card is still awaiting an answer — used to suppress
  // the "turn ended" notification (a pending permission means the agent is
  // blocked on you, not idle; that case is covered by the prompt notification).
  function _hasAskedPermission(): boolean {
    for (const block of blocks.value) {
      if (block.kind === "permission" && block.state === "asked") return true
    }
    return false
  }

  // Drop partKind entries no longer referenced by a live block so a long
  // multi-turn session doesn't accumulate stale ids forever.
  function _prunePartKind() {
    const live = new Set<string>()
    for (const block of blocks.value) {
      if (
        block.kind === "text" ||
        block.kind === "reasoning" ||
        block.kind === "tool"
      ) {
        live.add(block.partID)
      }
    }
    for (const key of Object.keys(partKind)) {
      if (!live.has(key)) delete partKind[key]
    }
  }

  // Route a parsed event to the right card. `session`/`session.status` carry no
  // transcript state (the transport owns the session id) — listed for
  // exhaustiveness.
  function handleEvent(event: OpencodeEvent) {
    switch (event.type) {
      case "message.part.delta":
        _appendDelta(event.properties.partID, event.properties.delta)
        break
      case "message.part.updated":
        _upsertPart(event.properties.part)
        break
      case "permission.asked":
        _pushPermission(event.properties)
        break
      case "permission.replied":
        _markReplied(event.properties.requestID, event.properties.reply)
        break
      case "error":
        showErrorToast(event.properties.message, "agent error")
        break
      case "session":
      case "session.status":
        break
    }
  }

  // Snapshot per-turn state when a turn begins: prune stale part ids and freeze
  // the permission count carried over from earlier turns (for the i/n indicator).
  function onTurnStart() {
    _prunePartKind()
    turnPermissionCount = permissionBlocks.value.length
  }

  // Turn ended: freeze unresolved cards, hold the view at the bottom, and fire
  // the idle notification — but only on a natural finish (not a user Stop, not a
  // failure) and only if nothing was awaiting an answer (a pending permission
  // means the agent isn't idle, it's blocked on you).
  function onTurnEnd({
    clean,
    userStopped,
    recovered = false,
    timedOut = false,
    cancelled = false,
  }: {
    clean: boolean
    userStopped: boolean
    recovered?: boolean
    timedOut?: boolean
    cancelled?: boolean
  }) {
    const hadPending = _hasAskedPermission()
    _freezePendingCards()
    _scrollToBottom()
    if (clean && !userStopped && !hadPending) {
      notify("Agent finished", "Awaiting your reply")
    } else if (recovered && !userStopped && !cancelled && !hadPending) {
      // The live stream dropped (deploy/daemon bounce) but the daemon kept the
      // turn and we reconciled its parts — tell a backgrounded user the reply
      // is here, without claiming idle (we reconciled, we didn't see idle).
      notify("Agent reply recovered", "Connection dropped — reply restored")
    } else if (timedOut && !userStopped && !cancelled && !hadPending) {
      // Recovery hit the 60s cap with a partial reply; the daemon may still be
      // running, so don't claim "restored".
      notify(
        "Agent reply may be incomplete",
        "Recovery timed out — the agent may still be running",
      )
    }
  }

  function pushUser(text: string) {
    blocks.value.push({ kind: "user", uid: crypto.randomUUID(), text })
  }

  // Replay persisted parts (from getSessionTranscript) into the transcript — after
  // a dropped stream or on page load. Each part is fed through the same upsert
  // path as a live `message.part.updated` event, so a partial block is filled in
  // and a missing one appended, idempotently by partID. User blocks aren't
  // reconstructed (they survive a drop locally; a full reload shows the agent's
  // parts only).
  function applyParts(parts: Part[]) {
    for (const part of parts) {
      handleEvent({ type: "message.part.updated", properties: { part } })
    }
    _scrollToBottom()
  }

  // Post-HTTP success flip for answerPermission (the page does the POST, then
  // calls this). Mirrors _markReplied's asked→answered transition.
  function markAnswered(block: PermissionBlock, reply: PermissionReply) {
    if (block.state === "asked") {
      block.state = "answered"
      block.answer = reply
    }
  }

  function _appendDelta(partID: string, delta: string) {
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
      _scrollToBottom()
      return
    }
    const block = reactive(
      kind === "reasoning"
        ? { kind: "reasoning" as const, partID, text: delta }
        : { kind: "text" as const, partID, text: delta },
    )
    blocks.value.push(block)
    partIndex.set(partID, block)
    _scrollToBottom()
  }

  function _upsertPart(part: Part) {
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
        const block = reactive({ kind: type, partID, text: part.text ?? "" })
        blocks.value.push(block)
        partIndex.set(partID, block)
        // The answer begins: reasoning traces are done, follow along.
        if (type === "text") _scrollToBottom()
      }
      return
    }
    if (type === "tool") {
      const state = part.state ?? {}
      const existing = partIndex.get(partID)
      const fields = {
        tool: part.tool ?? "",
        status: state.status ?? "",
        // `title` is the human tool label (opencode emits it on `state`).
        title: state.title,
        // Keep the raw input object (not stringified) so tool components read
        // fields directly; the generic fallback stringifies for display.
        input: state.input ?? {},
        output:
          state.output == null
            ? ""
            : typeof state.output === "string"
              ? state.output
              : JSON.stringify(state.output, null, 2),
      }
      if (existing && existing.kind === "tool") {
        Object.assign(existing, fields)
      } else {
        // reactive() so later Object.assign updates (status/input/output as the
        // tool runs) trigger re-renders — partIndex holds this same proxy.
        const block = reactive({ kind: "tool" as const, partID, ...fields })
        blocks.value.push(block)
        partIndex.set(partID, block)
        _scrollToBottom()
      }
    }
    // step-start / step-finish arrive as their own parts but aren't rendered.
  }

  function _pushPermission(asked: PermissionAsked) {
    // reactive() so _markReplied/markAnswered state flips trigger re-renders.
    const block = reactive(parsePermissionBlock(asked))
    const existing = permissionIndex.get(block.id)
    if (existing) {
      // opencode re-emits permission.asked (e.g. on a tool retry after reject).
      // Refresh the metadata AND reopen the card: reset state to "asked" so the
      // action buttons come back and a later permission.replied isn't dropped
      // by the `state === "asked"` gate. Clear any stale answer/pending.
      existing.permission = block.permission
      existing.command = block.command
      existing.filepath = block.filepath
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
    _scrollToBottom()
    notify("Agent needs approval", block.command || block.permission)
  }

  function _markReplied(requestID: string, reply: PermissionReply) {
    const block = _findPermission(requestID)
    if (!block) {
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
    block.requestId = requestID
    if (block.state === "asked") {
      block.state = "answered"
      block.answer = reply
    }
  }

  function _findPermission(id: string): PermissionBlock | undefined {
    const direct = permissionIndex.get(id)
    if (direct) return direct
    // Fall back to requestId: a replied event may carry a requestID that wasn't
    // the block's `id` (the id↔requestID contract is verified by an integration
    // test, but this keeps a divergence from silently losing the user's answer).
    for (const candidate of permissionIndex.values()) {
      if (candidate.requestId === id) return candidate
    }
    return undefined
  }

  // The single integration point with the transport: hand this to
  // conn.send(text, turnHooks). Bundles the three turn lifecycle hooks so the
  // page doesn't poke them individually.
  const turnHooks: TurnHooks = {
    onEvent: handleEvent,
    onTurnStart,
    onTurnEnd,
  }

  // Wipe the transcript window: blocks, lookup indexes, partKind map. Does NOT
  // touch the session — the page decides that (clear keeps it, reset drops it).
  function clear() {
    blocks.value = []
    partIndex.clear()
    permissionIndex.clear()
    for (const key of Object.keys(partKind)) delete partKind[key]
  }

  return {
    blocks,
    activePermission,
    activePermissionIndex,
    permissionTotal,
    turnHooks,
    pushUser,
    applyParts,
    markAnswered,
    clear,
  }
}
