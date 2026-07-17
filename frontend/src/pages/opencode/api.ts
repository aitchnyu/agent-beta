import axios from "axios"
import { OpencodeActionResponseSchema } from "../../schemas"
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
      await axios.post(`/api/opencode/permission/${sessionId}/${requestId}/`, {
        response: reply,
      })
    ).data,
  )
}

export async function postAbort(sessionId: string): Promise<void> {
  OpencodeActionResponseSchema.parse(
    (await axios.post(`/api/opencode/abort/${sessionId}/`)).data,
  )
}
