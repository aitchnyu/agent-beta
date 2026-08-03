import { z } from "zod"

// Validate the server payload shapes; parse() throws loudly if they drift.
export const NoteSchema = z.object({
  public_id: z.string(),
  title: z.string(),
  body: z.string(),
  owner_public_id: z.string(),
  owner_title: z.string(),
})

export type NoteOut = z.infer<typeof NoteSchema>

// The Inertia page data is nested under `props` (page.props.props).
export const NotesPagePropsSchema = z.object({ notes: NoteSchema.array() })
