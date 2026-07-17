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
      input: string
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
      always: string
      state: "asked" | "answered" | "cancelled"
      answer?: PermissionReply
      pending?: boolean
    }

export type PermissionBlock = Extract<Block, { kind: "permission" }>
export type PartBlock = Extract<Block, { kind: "text" | "reasoning" | "tool" }>

// Stable v-for key for any block kind. Namespaces are disjoint (uid is a UUID,
// partID is "par_…", permission ids are "per_…"), so the raw field works as a
// key without a kind prefix.
export function blockKey(b: Block): string {
  switch (b.kind) {
    case "user":
      return b.uid
    case "text":
    case "reasoning":
    case "tool":
      return b.partID
    case "permission":
      return b.id
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
export function parsePermissionBlock(p: PermissionAsked): PermissionBlock {
  return {
    kind: "permission",
    id: p.id,
    permission: p.permission,
    command: p.metadata?.command ?? "",
    always: p.always.join(" "),
    state: "asked",
  }
}
