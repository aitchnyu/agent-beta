import { z } from "zod"

// Facts feature's shared shapes — used by the three facts pages and Home
// (the Fact of the Day). Each page's own props schema is declared inline in
// the page component; only shapes shared across components live here.

export const TopicSchema = z.object({
  public_id: z.string(),
  name: z.string(),
  slug: z.string(),
})

export type TopicOut = z.infer<typeof TopicSchema>

export const FactSchema = z.object({
  public_id: z.string(),
  text: z.string(),
  topic: TopicSchema,
})

export type FactOut = z.infer<typeof FactSchema>
