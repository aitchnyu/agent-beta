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

// ---- Models (superuser read views over ourapp's concrete models) ----

export const ModelItemSchema = z.object({
  name: z.string(),
  docstring: z.string(),
  row_count: z.number(),
})

export const ModelListPropsSchema = z.object({
  models: z.array(ModelItemSchema),
})

export type ModelListProps = z.infer<typeof ModelListPropsSchema>

// ---- Row list / detail (a model's rows) ----

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

// A foreign_key cell value: the referenced row, linked via get_absolute_url().
export const FkValueSchema = z.object({
  public_id: z.string(),
  url: z.string(),
  title: z.string(),
})

export type FkValue = z.infer<typeof FkValueSchema>

// Cell values keyed by column name. The frontend casts each cell by its column
// type (looked up via columns): user cells are a {public_id, title} profile or
// null, foreign_key cells are an FkValue or null, decimal/datetime cells are
// strings, others are raw.
export const RowValuesSchema = z.record(z.string(), z.unknown())

export const RowListColumnDefSchema = z.object({
  name: z.string(),
  type: RowColumnTypeSchema,
  has_choices: z.boolean(),
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

export const ModelRowsPropsSchema = z.object({
  model_name: z.string(),
  columns: z.array(RowListColumnDefSchema),
  rows: z.array(RowListItemSchema),
  pagination: RowListPaginationSchema,
  filters: RowListFiltersSchema,
})

export const RowDetailPropsSchema = z.object({
  model_name: z.string(),
  public_id: z.string(),
  columns: z.array(RowListColumnDefSchema),
  values: RowValuesSchema,
  created_by: UserSchema.nullable(),
  created_at: z.string(),
  edited_at: z.string(),
})

// opencode daemon: one SSE frame re-emitted by Django from opencode's /event
// stream (filtered to this session). The client dispatches on `type`.
//
// Each branch validates the fields the client actually reads and uses
// `.passthrough()` so opencode adding fields doesn't break parsing — and a
// malformed required field fails loudly (the frame is dropped via safeParse in
// useOpencodeChat) instead of mutating state with `undefined` via an `as` cast.

// A `message.part.updated` part. Variants share one shape; readers route on
// `type`. `id` is required — a part without it is useless (its deltas would
// collide on the empty-string key) so such a frame is dropped by the parser.
const PartStateSchema = z
  .object({
    status: z.string().optional(),
    input: z.unknown().optional(),
    output: z.unknown().optional(),
    metadata: z.unknown().optional(),
  })
  .passthrough()

export const PartSchema = z
  .object({
    id: z.string(),
    type: z
      .enum(["text", "reasoning", "tool", "step-start", "step-finish"])
      .default("text"),
    text: z.string().optional(),
    tool: z.string().optional(),
    state: PartStateSchema.optional(),
  })
  .passthrough()

export type Part = z.infer<typeof PartSchema>

// `permission.asked` properties. `metadata` may be null for some permission
// types (opencode emits it so); `always` is a list of suggested always-allow
// patterns.
export const PermissionAskedSchema = z
  .object({
    id: z.string(),
    permission: z.string(),
    metadata: z
      .object({ command: z.string().optional() })
      .passthrough()
      .nullish(),
    always: z.array(z.string()).default([]),
  })
  .passthrough()

export type PermissionAsked = z.infer<typeof PermissionAskedSchema>

export const OpencodeEventSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("session"),
    // Snake_case `session_id` because Django synthesizes this event (opencode's
    // own events use camelCase `sessionID` — filtered server-side).
    properties: z.object({ session_id: z.string() }).passthrough(),
  }),
  z.object({
    type: z.literal("error"),
    properties: z.object({ message: z.string() }).passthrough(),
  }),
  z.object({
    type: z.literal("message.part.delta"),
    properties: z
      .object({ partID: z.string(), delta: z.string().default("") })
      .passthrough(),
  }),
  z.object({
    type: z.literal("message.part.updated"),
    properties: z.object({ part: PartSchema }).passthrough(),
  }),
  z.object({
    type: z.literal("permission.asked"),
    properties: PermissionAskedSchema,
  }),
  z.object({
    type: z.literal("permission.replied"),
    properties: z
      .object({
        requestID: z.string(),
        reply: z.enum(["once", "always", "reject"]),
      })
      .passthrough(),
  }),
  z.object({
    type: z.literal("session.status"),
    // Not read by the client (Django closes the stream on idle). Keep loose.
    properties: z.record(z.string(), z.unknown()).optional(),
  }),
])

export type OpencodeEvent = z.infer<typeof OpencodeEventSchema>

// Generic `{ok: bool}` reply from the opencode proxy (permission / abort). The
// proxy returns HTTP 502 on failure, so on a 200 `ok` is always true — the
// schema validates shape only.
export const OpencodeActionResponseSchema = z.object({
  ok: z.boolean(),
})

// ---- File browser (/files/...) — superuser-only ----

export const FileCrumbSchema = z.object({
  label: z.string(),
  rel: z.string(),
})

export const FileEntrySchema = z.object({
  name: z.string(),
  is_dir: z.boolean(),
  is_image: z.boolean(),
  size: z.number(), // bytes — formatted client-side (humanized)
  mtime: z.number(), // epoch ms — formatted client-side in the local timezone
})

export const FileBrowserPropsSchema = z.object({
  rel: z.string(),
  breadcrumb: z.array(FileCrumbSchema),
  parent: z.string().nullable(),
  entries: z.array(FileEntrySchema),
  contains_hidden_entries: z.boolean(),
})

export const FileViewerPropsSchema = z.object({
  rel: z.string(),
  breadcrumb: z.array(FileCrumbSchema),
  parent: z.string(),
  name: z.string(),
  size: z.number(),
  mtime: z.number(),
  kind: z.enum(["text", "image", "binary", "markdown"]),
  text: z.string().default(""),
})

// --- /git viewer (project repo) ---
export const GitUncommittedFileSchema = z.object({
  path: z.string(),
  status: z.string(),
})

export const GitCommitSummarySchema = z.object({
  sha: z.string(),
  short_sha: z.string(),
  author: z.string(),
  date: z.number(), // epoch ms — rendered via HumanizedTime
  subject: z.string(),
})

export const GitCommitFileSchema = z.object({
  path: z.string(),
  status: z.string(),
})

export const GitPaginationSchema = z.object({
  page: z.number(),
  total_pages: z.number(),
  total_count: z.number(),
})

export const GitDiffPropsSchema = z.object({
  title: z.string(),
  diff: z.string(),
})

export const GitUncommittedPropsSchema = z.object({
  files: z.array(GitUncommittedFileSchema),
})

export const GitCommitListPropsSchema = z.object({
  commits: z.array(GitCommitSummarySchema),
  pagination: GitPaginationSchema,
})

export const GitCommitPropsSchema = z.object({
  commit: GitCommitSummarySchema,
  files: z.array(GitCommitFileSchema),
})
