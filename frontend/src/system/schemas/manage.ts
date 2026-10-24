import { z } from "zod"
import { UserSchema } from "./sharedProps"

// Manage feature's zod schemas (system/pages/manage/*): the model list, row
// list, and row detail pages' props plus the column/value sub-schemas that
// RowCell.vue (system/components/manage) renders.

// ---- Model list page ----

const ModelItemSchema = z.object({
  name: z.string(),
  docstring: z.string(),
  row_count: z.number(),
})

export const ModelListPropsSchema = z.object({
  models: z.array(ModelItemSchema),
})

// ---- Row list/detail pages ----

const RowColumnTypeSchema = z.enum([
  "char",
  "text",
  "integer",
  "boolean",
  "decimal",
  "datetime",
  "user",
  "foreign_key",
])

export const RowListColumnDefSchema = z.object({
  name: z.string(),
  type: RowColumnTypeSchema,
  has_choices: z.boolean(),
})

export type RowListColumnDef = z.infer<typeof RowListColumnDefSchema>

// A foreign_key cell value: the referenced row, linked via get_absolute_url().
export const FkValueSchema = z.object({
  public_id: z.string(),
  url: z.string(),
  title: z.string(),
})

// Cell values keyed by column name. The frontend casts each cell by its column
// type (looked up via columns): user cells are a {public_id, title} profile or
// null, foreign_key cells are an FkValue or null, decimal/datetime cells are
// strings, others are raw.
const RowValuesSchema = z.record(z.string(), z.unknown())

const RowListItemSchema = z.object({
  // null for non-BaseModel rows (no detail link).
  public_id: z.string().nullable(),
  values: RowValuesSchema,
})

const RowListPaginationSchema = z.object({
  page: z.number(),
  total_pages: z.number(),
  total_count: z.number(),
})

const RowListFiltersSchema = z.object({
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
})

// An audit-log entry (one per create/update/delete). FK values inside
// old_values/new_values are {id, url, name}; numbers are strings; datetimes ISO.
export const UpdateLogEntryItemSchema = z.object({
  id: z.string(),
  action: z.enum(["created", "updated", "deleted"]),
  performed_by: UserSchema.nullable(),
  performed_at: z.string(),
  old_values: RowValuesSchema,
  new_values: RowValuesSchema,
})

export type UpdateLogEntryItem = z.infer<typeof UpdateLogEntryItemSchema>
