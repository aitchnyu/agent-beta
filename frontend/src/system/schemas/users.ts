import { z } from "zod"

// Users feature's zod schemas (system/pages/users/*): the four pages' props
// plus the API response shapes they parse. Keyed pk-free: public_id only.

// ---- List page ----

const UserListItemSchema = z.object({
  public_id: z.string(),
  first_name: z.string(),
  last_name: z.string(),
  username: z.string(),
  email: z.string(),
  has_public_profile: z.boolean(),
  is_active: z.boolean(),
  is_staff: z.boolean(),
  is_superuser: z.boolean(),
})

export const UserListPropsSchema = z.object({
  path_prefix: z.string(),
  users: z.array(UserListItemSchema),
  pagination: z.object({
    page: z.number(),
    total_pages: z.number(),
    total_count: z.number(),
  }),
  filters: z.object({
    page: z.number(),
    q: z.string(),
  }),
})

// ---- List page: live search ----

export const UserSearchItemSchema = z.object({
  public_id: z.string(),
  username: z.string(),
  title: z.string(),
})

export const UserSearchResponseSchema = z.object({
  users: z.array(UserSearchItemSchema),
})

// ---- Detail page ----

export const UserDetailsPropsSchema = z.object({
  path_prefix: z.string(),
  public_id: z.string(),
  first_name: z.string(),
  last_name: z.string(),
  username: z.string().nullable(),
  description: z.string().nullable(),
  is_owner: z.boolean(),
  email: z.string().nullable(),
  has_public_profile: z.boolean(),
  is_active: z.boolean(),
  is_staff: z.boolean(),
  is_superuser: z.boolean(),
  history_count: z.number(),
  // Admin-only (superuser viewers): null when not populated.
  last_login: z.string().nullable(),
  session_count: z.number(),
})

// POST reply of the admin login-link action.
export const LoginLinkResponseSchema = z.object({
  url: z.string(),
  expires_at: z.string(),
})

// POST reply of the admin logout-everywhere action.
export const LogoutResponseSchema = z.object({ sessions: z.number() })

// ---- Edit page ----

export const UserEditItemSchema = z.object({
  public_id: z.string(),
  username: z.string(),
  first_name: z.string(),
  last_name: z.string(),
  email: z.string(),
  description: z.string(),
  has_public_profile: z.boolean(),
  is_active: z.boolean(),
  is_staff: z.boolean(),
  is_superuser: z.boolean(),
})

export const UserEditPropsSchema = z.object({
  path_prefix: z.string(),
  target: UserEditItemSchema,
})

// POST reply of the edit action: the saved row's public id.
export const UserMessageResponseSchema = z.object({ id: z.string() })

// ---- History page ----

const UserStringChangeSchema = z.object({ old: z.string(), new: z.string() })
const UserBoolChangeSchema = z.object({ old: z.boolean(), new: z.boolean() })

const UserHistoryChangesSchema = z.object({
  first_name: UserStringChangeSchema.nullable(),
  last_name: UserStringChangeSchema.nullable(),
  email: UserStringChangeSchema.nullable(),
  description: UserStringChangeSchema.nullable(),
  has_public_profile: UserBoolChangeSchema.nullable(),
  is_active: UserBoolChangeSchema.nullable(),
  is_staff: UserBoolChangeSchema.nullable(),
  is_superuser: UserBoolChangeSchema.nullable(),
  // Admin-action payloads (login_link, logout_all), not field diffs.
  login_link_minutes: z.number().nullable(),
  logout_all_sessions: z.number().nullable(),
})

export const UserHistoryEntrySchema = z.object({
  public_id: z.string(),
  action: z.enum([
    "created",
    "edited",
    "deleted",
    "login",
    "login_link",
    "logout_all",
  ]),
  time: z.string(),
  changes: UserHistoryChangesSchema,
})

export const UserHistoryPropsSchema = z.object({
  path_prefix: z.string(),
  target_public_id: z.string(),
  target_title: z.string(),
  entries: z.array(UserHistoryEntrySchema),
})
