// MAINTAIN-CONSISTENCY repo-map: excerpted in .pi/repo-map.md §9 — change both together.
// ILLUSTRATIVE — hand-written stand-in. Generate the real file in the
// overlay scratch (README §Workflow), where this app is importable:
//   cd ../scratch && ./run djangomanage generatesdk ourapp.views frontend/src/app/schemas/ourapp_sdk.ts
// One file per NinjaAPI; this per-feature split is for readability.

import { z } from "zod"
import { ninjaPost } from "@/system/utils/http"

export const TodoOutSchema = z.object({
  public_id: z.string(),
  text: z.string(),
  completed: z.boolean(),
  // Optimistic-lock version: echo it back as expected_row_version on the
  // next mutating request; a stale number gets a 404.
  row_version: z.number().int(),
  owner_public_id: z.string(),
})

export const TodoCreateSchema = z.object({
  text: z.string().min(1),
  expected_row_version: z.number().int(),
})

export const TodoToggleSchema = z.object({
  expected_row_version: z.number().int(),
})

export const post_create_todo = (body: z.input<typeof TodoCreateSchema>) =>
  ninjaPost(TodoOutSchema, `/todos/create`, body)

export const post_toggle_todo = (
  publicId: string,
  body: z.input<typeof TodoToggleSchema>,
) => ninjaPost(TodoOutSchema, `/todos/${publicId}/toggle`, body)
