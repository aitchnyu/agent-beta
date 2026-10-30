// MAINTAIN-CONSISTENCY repo-map: excerpted in .pi/repo-map.md §9 — change both together.

import { z } from "zod"

// Todos feature's shared shape — the list page and the form component both
// parse rows through it. The page's own props schema is declared inline in
// the page component; only the shared row shape lives here.

export const TodoSchema = z.object({
  public_id: z.string(),
  text: z.string(),
  completed: z.boolean(),
  // Optimistic-lock version: echo it back on the next mutating request as
  // expected_row_version; a stale number gets a 404 — the row
  // changed since this read.
  row_version: z.number().int().nonnegative(),
  owner_public_id: z.string(),
})

export type TodoOut = z.infer<typeof TodoSchema>
