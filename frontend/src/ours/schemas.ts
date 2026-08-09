import { z } from "zod"

// Validate the server payload shapes; parse() throws loudly if they drift.

// ---- Home ----

// The landing page's props (ours/Home). pk-free: only the public_id is sent.
export const HomePropsSchema = z.object({
  is_authenticated: z.boolean(),
  display_name: z.string(),
  public_id: z.string(),
})

export type HomeProps = z.infer<typeof HomePropsSchema>
