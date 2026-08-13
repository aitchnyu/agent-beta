import axios from "axios"
import { z } from "zod"
import { OpencodeActionResponseSchema, PartSchema } from "../../schemas"
import type { Part } from "../../schemas"
import type { PermissionReply } from "./types"

// Pure HTTP wrappers around the opencode proxy endpoints. Each resolves on
// success and throws on a non-2xx reply (the proxy returns 502 on opencode
// failure, which axios raises before this parse runs) or a network error. The
// `OpencodeActionResponseSchema.parse` only validates the success body's shape
// — on a 200 `ok` is always true, so there's no `if (!res.ok)` branch here. No
// Vue, no toast, no state — callers own UI and reconciliation. CSRF is attached
// globally via axios.defaults (see main.ts), so no explicit header here.

export async function postPermission(
  sessionId: string,
  requestId: string,
  reply: PermissionReply,
): Promise<void> {
  OpencodeActionResponseSchema.parse(
    (
      await axios.post(`/agent/api/permission/${sessionId}/${requestId}/`, {
        response: reply,
      })
    ).data,
  )
}

export async function postAbort(sessionId: string): Promise<void> {
  OpencodeActionResponseSchema.parse(
    (await axios.post(`/agent/api/abort/${sessionId}/`)).data,
  )
}

// Delete the session on the daemon
// Used by the "Reset session" button to free the daemon's conversation
// history/context, not just drop the client's handle.
export async function postDeleteSession(sessionId: string): Promise<void> {
  OpencodeActionResponseSchema.parse(
    (await axios.post(`/agent/api/delete/${sessionId}/`)).data,
  )
}

// One persisted message from the daemon's history. `role` (under `info`) is the
// message author — used to drop user turns so they aren't replayed as agent
// text (the current user message is already in the transcript via pushUser, and
// prior user turns aren't reconstructed). Other `info` fields are ignored.
const SessionMessageSchema = z.object({
  info: z.object({ role: z.string().optional() }).optional(),
  parts: z.array(PartSchema).default([]),
})

// Fetch the daemon's persisted transcript for a session — the replay source
// after a dropped stream (application reload, daemon bounce) and on page load.
// Returns the assistant parts in order (user turns are dropped so they aren't
// re-rendered as agent output); the caller feeds them through the transcript's
// upsert path to recover whatever the live stream missed. Throws on a non-2xx
// (the proxy returns 502 when the daemon is down).
export async function getSessionTranscript(
  sessionId: string,
  opts: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<Part[]> {
  // Build the config conditionally so we never pass `undefined` for signal /
  // timeout (the project enables exactOptionalPropertyTypes).
  const config: { signal?: AbortSignal; timeout?: number } = {}
  if (opts.signal) config.signal = opts.signal
  if (opts.timeoutMs) config.timeout = opts.timeoutMs
  const resp = await axios.get(
    `/agent/api/session/${sessionId}/transcript/`,
    config,
  )
  const messages = z.array(SessionMessageSchema).parse(resp.data)
  return messages.filter((m) => m.info?.role !== "user").flatMap((m) => m.parts)
}
