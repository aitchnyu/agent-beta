// ILLUSTRATIVE — hand-written stand-in. Generate the real file in the
// overlay scratch (README §Workflow), where this app is importable:
//   cd ../scratch && ./run djangomanage generatesdk ourapp.views frontend/src/app/schemas/ourapp_sdk.ts
// One file per NinjaAPI; this per-feature split is for readability. Facts
// endpoints render pages, so this split holds schemas only — no functions.

import { z } from "zod"

export const TopicOutSchema = z.object({
  public_id: z.string(),
  name: z.string(),
  slug: z.string(),
})

export const FactOutSchema = z.object({
  public_id: z.string(),
  text: z.string(),
  topic: TopicOutSchema,
})
