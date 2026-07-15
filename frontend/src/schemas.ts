import { z } from "zod"

export const HomePropsSchema = z.object({
  is_authenticated: z.boolean(),
  display_name: z.string(),
  public_id: z.string(),
})

export type HomeProps = z.infer<typeof HomePropsSchema>

// Profile user (shared prop + list/detail rows). pk-free: only public_id.
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
  target_public_id: z.string(),
  target_title: z.string(),
  entries: z.array(UserHistoryEntrySchema),
})

export const MessageResponseSchema = z.object({ id: z.string() })

// ---- Shared props (Inertia shared, injected by SharedPropsMiddleware) ----

// Read via usePage().props on every page; pk-free (public_id only).
export const SharedPropsSchema = z.object({
  user: UserSchema.nullable(),
  viewer_is_superuser: z.boolean(),
})

export type SharedProps = z.infer<typeof SharedPropsSchema>

// ---- Applications (superuser read views) ----

export const CollectionItemSchema = z.object({
  name: z.string(),
})

export const CollectionsPropsSchema = z.object({
  collections: z.array(CollectionItemSchema),
})

export const AppItemSchema = z.object({
  name: z.string(),
})

export const AppListPropsSchema = z.object({
  collection_name: z.string(),
  apps: z.array(AppItemSchema),
})

export const TableItemSchema = z.object({
  name: z.string(),
  row_count: z.number(),
})

export const ManagePropsSchema = z.object({
  collection_name: z.string(),
  app_name: z.string(),
  tables: z.array(TableItemSchema),
})

// ---- Row list / detail (superuser read views on a table's dynamic model) ----

export const RowColumnTypeSchema = z.enum([
  "char",
  "text",
  "integer",
  "boolean",
  "decimal",
  "datetime",
  "user",
  "foreign_key",
])

// The table a foreign_key column points at (lets a cell link to a target row).
export const FkTargetSchema = z.object({
  collection_name: z.string(),
  app_name: z.string(),
  table_name: z.string(),
})

export type FkTarget = z.infer<typeof FkTargetSchema>

// A foreign_key cell value: the referenced row's public_id (or null when unset).
export const FkCellValueSchema = z.object({
  public_id: z.string(),
})

export type FkCellValue = z.infer<typeof FkCellValueSchema>

// Cell values keyed by column name. Frontend casts each cell by its column
// type (looked up via columns): user cells are a {public_id, title} profile
// or null, decimal/datetime cells are strings, foreign_key cells are a
// {public_id} ref or null, others are raw.
export const RowValuesSchema = z.record(z.string(), z.unknown())

export const RowListColumnDefSchema = z.object({
  name: z.string(),
  type: RowColumnTypeSchema,
  has_choices: z.boolean(),
  fk_target: FkTargetSchema.nullable().default(null),
})

export type RowListColumnDef = z.infer<typeof RowListColumnDefSchema>

export const RowListItemSchema = z.object({
  public_id: z.string(),
  values: RowValuesSchema,
  created_by: UserSchema.nullable(),
  created_at: z.string(),
  edited_at: z.string(),
})

export const RowListPaginationSchema = z.object({
  page: z.number(),
  total_pages: z.number(),
  total_count: z.number(),
})

export const RowListFiltersSchema = z.object({
  per_page: z.number(),
  page: z.number(),
  sort: z.string(),
})

export const RowListPropsSchema = z.object({
  collection_name: z.string(),
  app_name: z.string(),
  table_name: z.string(),
  columns: z.array(RowListColumnDefSchema),
  rows: z.array(RowListItemSchema),
  pagination: RowListPaginationSchema,
  filters: RowListFiltersSchema,
})

export const RowDetailPropsSchema = z.object({
  collection_name: z.string(),
  app_name: z.string(),
  table_name: z.string(),
  public_id: z.string(),
  columns: z.array(RowListColumnDefSchema),
  values: RowValuesSchema,
  created_by: UserSchema.nullable(),
  created_at: z.string(),
  edited_at: z.string(),
})
