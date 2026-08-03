// View-model types for the opencode chat page. These describe the cards the
// transcript renders — not the wire shape of SSE events (that lives in
// schemas.ts as OpencodeEventSchema). The pure parser below converts a parsed
// event's `properties` into one of these blocks; the page handles the reactive
// list mutation and network calls.

import type { PermissionAsked } from "../../schemas"

export type PermissionReply = "once" | "always" | "reject"

export type Block =
  // `uid` so a user block has a stable v-for key (no natural id); the
  // transcript is append-only today but Vue must not reuse a stateful child
  // across different blocks.
  | { kind: "user"; uid: string; text: string }
  | { kind: "text"; partID: string; text: string }
  | { kind: "reasoning"; partID: string; text: string }
  | {
      kind: "tool"
      partID: string
      tool: string
      status: string
      // Human label for the part (e.g. "Write to …", "Run command"); arrives
      // via Part passthrough, captured in upsertPart. Optional — some omit it.
      title?: string | undefined
      // The raw tool input object (not stringified) so tool components can read
      // fields directly (write: {filePath, content}; edit: {filePath, oldString,
      // newString}; bash: {command, …}).
      input: unknown
      output: string
    }
  | {
      kind: "permission"
      id: string
      // `requestID` from `permission.replied` if it ever differs from `id`;
      // populated when observed so a later reply can still find this block.
      requestId?: string
      permission: string
      command: string
      // write/edit target (from metadata.filepath); bash leaves this empty and
      // uses `command` instead.
      filepath: string
      always: string
      state: "asked" | "answered" | "cancelled"
      answer?: PermissionReply
      pending?: boolean
    }

export type PermissionBlock = Extract<Block, { kind: "permission" }>
export type PartBlock = Extract<Block, { kind: "text" | "reasoning" | "tool" }>
export type ToolBlock = Extract<Block, { kind: "tool" }>

// Stable v-for key for any block kind. Namespaces are disjoint (uid is a UUID,
// partID is "par_…", permission ids are "per_…"), so the raw field works as a
// key without a kind prefix.
export function blockKey(block: Block): string {
  switch (block.kind) {
    case "user":
      return block.uid
    case "text":
    case "reasoning":
    case "tool":
      return block.partID
    case "permission":
      return block.id
  }
}

// Human label for the recorded permission answer (the wire enum reads poorly
// in the UI: "Answered: reject").
export const PERMISSION_LABELS: Record<PermissionReply, string> = {
  once: "Allowed once",
  always: "Allowed always",
  reject: "Rejected",
}

// Build a permission block from a parsed `permission.asked` event's properties.
export function parsePermissionBlock(asked: PermissionAsked): PermissionBlock {
  const meta = asked.metadata ?? {}
  return {
    kind: "permission",
    id: asked.id,
    permission: asked.permission,
    // bash carries `command`; write/edit carry `filepath`. Show whichever the
    // tool sent so the marker matches the corresponding tool block's subject.
    command: meta.command ?? "",
    filepath: meta.filepath ?? "",
    always: asked.always.join(" "),
    state: "asked",
  }
}
