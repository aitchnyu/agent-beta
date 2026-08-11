import { z } from "zod"

// Validate the server payload shapes; parse() throws loudly if they drift.

// ---- Facts (shared shapes) ----

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

// ---- Home ----

// The landing page's props (ours/Home). pk-free: only the public_id is sent.
// fact_of_day is today's fixed pick (chosen by a Huey daily cron) or null.
export const HomePropsSchema = z.object({
  is_authenticated: z.boolean(),
  display_name: z.string(),
  public_id: z.string(),
  fact_of_day: FactSchema.nullable(),
})

export type HomeProps = z.infer<typeof HomePropsSchema>

// ---- Facts pages ----

// The Inertia page data is nested under `props` (page.props.props).
export const FactsPagePropsSchema = z.object({
  fact: FactSchema.nullable(),
  topics: TopicSchema.array(),
})

export const FactTopicPagePropsSchema = z.object({
  topic: TopicSchema,
  fact: FactSchema.nullable(),
  topics: TopicSchema.array(),
})

// One specific fact by public_id (a stable permalink; non-null or the route 404s).
export const FactPagePropsSchema = z.object({
  fact: FactSchema,
  topics: TopicSchema.array(),
})

// ---- Todos ----

export const TodoSchema = z.object({
  public_id: z.string(),
  text: z.string(),
  completed: z.boolean(),
  owner_public_id: z.string(),
})

export type TodoOut = z.infer<typeof TodoSchema>

export const TodosPagePropsSchema = z.object({
  todos: TodoSchema.array(),
})
