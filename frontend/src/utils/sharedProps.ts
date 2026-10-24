import { z } from "zod"

// Profile user (shared prop + list/detail rows). pk-free: only public_id.
export const UserSchema = z.object({
  public_id: z.string(),
  title: z.string(),
})

export type User = z.infer<typeof UserSchema>

// Shared props (Inertia shared, injected by SharedPropsMiddleware).
// Read via usePage().props on every page; pk-free (public_id only).
export const SharedPropsSchema = z.object({
  user: UserSchema.nullable(),
  viewer_is_superuser: z.boolean(),
  // Null when signed in (the dropdown never renders); anonymous gets the list.
  login_providers: z
    .array(z.object({ id: z.string(), name: z.string(), url: z.string() }))
    .nullable(),
  // The navbar user menu's badge (UserMenu.vue); static 0 when anonymous.
  unread_notifications: z.number(),
  // One-shot: true only on the landing render after login (the user menu
  // rebinds the browser's push subscription on it).
  just_logged_in: z.boolean(),
})
