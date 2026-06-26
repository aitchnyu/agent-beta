import { z } from "zod"

export const HomePropsSchema = z.object({
  is_authenticated: z.boolean(),
  display_name: z.string(),
  public_id: z.string(),
})

export type HomeProps = z.infer<typeof HomePropsSchema>

// Navbar/profile user. pk-free: only the URL-safe public_id is exposed.
export const UserSchema = z.object({
  public_id: z.string(),
  title: z.string(),
})

export type User = z.infer<typeof UserSchema>

export const UserListItemSchema = z.object({
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

export const UserListPaginationSchema = z.object({
  page: z.number(),
  total_pages: z.number(),
  total_count: z.number(),
})

export const UserListFiltersSchema = z.object({
  page: z.number(),
  q: z.string(),
})

export const UserListPropsSchema = z.object({
  path_prefix: z.string(),
  user: UserSchema.nullable(),
  users: z.array(UserListItemSchema),
  pagination: UserListPaginationSchema,
  filters: UserListFiltersSchema,
})

export const UserSearchItemSchema = z.object({
  public_id: z.string(),
  username: z.string(),
  title: z.string(),
})

export const UserSearchResponseSchema = z.object({
  users: z.array(UserSearchItemSchema),
})

export type UserSearchItem = z.infer<typeof UserSearchItemSchema>

export const UserDetailsPropsSchema = z.object({
  path_prefix: z.string(),
  public_id: z.string(),
  user: UserSchema.nullable(),
  first_name: z.string(),
  last_name: z.string(),
  username: z.string().nullable(),
  description: z.string().nullable(),
  is_owner: z.boolean(),
  viewer_is_superuser: z.boolean(),
  email: z.string().nullable(),
  has_public_profile: z.boolean(),
  is_active: z.boolean(),
  is_staff: z.boolean(),
  is_superuser: z.boolean(),
  history_count: z.number(),
})

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
  user: UserSchema.nullable(),
  target: UserEditItemSchema,
})

const UserStringChangeSchema = z.object({ old: z.string(), new: z.string() })
const UserBoolChangeSchema = z.object({ old: z.boolean(), new: z.boolean() })

export const UserHistoryChangesSchema = z.object({
  first_name: UserStringChangeSchema.nullable(),
  last_name: UserStringChangeSchema.nullable(),
  email: UserStringChangeSchema.nullable(),
  description: UserStringChangeSchema.nullable(),
  has_public_profile: UserBoolChangeSchema.nullable(),
  is_active: UserBoolChangeSchema.nullable(),
  is_staff: UserBoolChangeSchema.nullable(),
  is_superuser: UserBoolChangeSchema.nullable(),
})

export const UserHistoryEntrySchema = z.object({
  public_id: z.string(),
  action: z.enum(["created", "edited", "deleted"]),
  time: z.string(),
  changes: UserHistoryChangesSchema,
})

export const UserHistoryPropsSchema = z.object({
  path_prefix: z.string(),
  user: UserSchema.nullable(),
  target_public_id: z.string(),
  target_title: z.string(),
  entries: z.array(UserHistoryEntrySchema),
})

export const MessageResponseSchema = z.object({ id: z.string() })
