// ILLUSTRATIVE — hand-written stand-in. Generate the real file in the
// overlay scratch (README §Workflow), where this app is importable:
//   cd ../scratch && ./run djangomanage generatesdk ourapp.views frontend/src/app/schemas/ourapp_sdk.ts
// One file per NinjaAPI; this per-feature split is for readability.

import { z } from "zod"
import { ninjaPost } from "@/system/utils/http"

export const DownloadOutSchema = z.object({
  public_id: z.string(),
  original_name: z.string(),
  stored_name: z.string(),
  expires_at: z.string(),
  is_expired: z.boolean(),
  // Optimistic-lock echo for replace (deletes carry no version).
  row_version: z.number().int(),
})

export const DownloadDeletedSchema = z.object({
  deleted: z.string(),
})

// The upload/replace endpoints take multipart form data — the generator
// doesn't emit FormData calls yet, so those two stay on postForm in the page.
export const post_delete_download = (publicId: string) =>
  ninjaPost(DownloadDeletedSchema, `/downloads/${publicId}/delete`)
