import { z } from "zod"

// Backend uses exclude_none=True (Ninja Router), so None values are absent from JSON.
// Frontend schemas need .optional() (missing key) + .nullable() (explicit null) for these fields.
const nullableOptional = <T extends z.ZodTypeAny>(schema: T) =>
  schema.nullable().optional()

// Each of them has a corresponding Pydantic schema with the same name in responses.py.
// For example:
//
// class DebugViewSchema(BaseModel):
//     views: list[str]
//     user: Optional[UserSchema]
//
// export const DebugViewSchema = z.object({
//   views: z.array(z.string()),
//   user: z.nullable(UserSchema)
// })

export const UserSchema = z.object({
  id: z.number(),
  // Optional: only article UserProfile references carry a public_id (for
  // profile links). The tables UserSchema (navbar, row-update actors) does
  // not, so this stays optional to parse both shapes.
  // TODO make it required
  public_id: z.string().optional(),
  title: z.string(),
})

export const DebugViewSchema = z.object({
  table_urls: z.array(z.object({ name: z.string(), url: z.string() })),
  user: UserSchema.nullable(),
})

export interface User {
  id: number
  title: string
}

const CharFieldBase = z.object({
  name: z.string(),
  required: z.boolean(),
  max_length: z.number(),
  choices: z
    .array(z.object({ value: z.string(), label: z.string() }))
    .nullable(),
  default: z.string().nullable(),
})

const TextFieldBase = z.object({
  name: z.string(),
  required: z.boolean(),
  length: z.number(),
  default: z.string().nullable(),
})

const IntegerFieldBase = z.object({
  name: z.string(),
  required: z.boolean(),
  choices: z
    .array(z.object({ value: z.string(), label: z.string() }))
    .nullable(),
  default: z.number().nullable(),
})

const BooleanFieldBase = z.object({
  name: z.string(),
  required: z.boolean(),
  default: z.boolean().nullable(),
})

const DecimalFieldBase = z.object({
  name: z.string(),
  required: z.boolean(),
  decimal_places: z.number(),
  default: z.string().nullable(),
})

const DateTimeFieldBase = z.object({
  name: z.string(),
  required: z.boolean(),
  default: z.string().nullable(),
})

const ForeignKeyFieldBase = z.object({
  name: z.string(),
  required: z.boolean(),
  view_name: z.string(),
  default: z.object({ id: z.string(), text: z.string() }).nullable(),
})

const FileFieldBase = z.object({
  name: z.string(),
  required: z.boolean(),
})

export const CharFieldSchema = CharFieldBase.extend({
  d: z.literal("char"),
})

export const TextFieldSchema = TextFieldBase.extend({
  d: z.literal("text"),
})

export const IntegerFieldSchema = IntegerFieldBase.extend({
  d: z.literal("integer"),
})

export const BooleanFieldSchema = BooleanFieldBase.extend({
  d: z.literal("boolean"),
})

export const DecimalFieldSchema = DecimalFieldBase.extend({
  d: z.literal("decimal"),
})

export const DateTimeFieldSchema = DateTimeFieldBase.extend({
  d: z.literal("datetime"),
})

export const FileFieldSchema = FileFieldBase.extend({
  d: z.literal("file"),
})

export const ForeignKeyFieldSchema = ForeignKeyFieldBase.extend({
  d: z.literal("foreignkey"),
})

export const FieldSchema = z.discriminatedUnion("d", [
  CharFieldSchema,
  TextFieldSchema,
  IntegerFieldSchema,
  BooleanFieldSchema,
  DecimalFieldSchema,
  DateTimeFieldSchema,
  FileFieldSchema,
  ForeignKeyFieldSchema,
])

// ------------------ InputSchema ---------------------

const CharFieldInputBase = z.object({
  d: z.literal("char"),
  component: z.string(),
  name: z.string(),
  required: z.boolean(),
  max_length: z.number().nullable(),
  choices: z
    .array(z.object({ value: z.string(), label: z.string() }))
    .nullable(),
  default: z.string().nullable(),
})

const TextFieldInputBase = z.object({
  d: z.literal("text"),
  component: z.string(),
  name: z.string(),
  required: z.boolean(),
  length: z.number(),
  default: z.string().nullable(),
})

const IntegerFieldInputBase = z.object({
  d: z.literal("integer"),
  component: z.string(),
  name: z.string(),
  required: z.boolean(),
  choices: z
    .array(z.object({ value: z.string(), label: z.string() }))
    .nullable(),
  default: z.number().nullable(),
})

const BooleanFieldInputBase = z.object({
  d: z.literal("boolean"),
  component: z.string(),
  name: z.string(),
  required: z.boolean(),
  default: z.boolean().nullable(),
})

const DecimalFieldInputBase = z.object({
  d: z.literal("decimal"),
  component: z.string(),
  name: z.string(),
  required: z.boolean(),
  decimal_places: z.number(),
  default: z.string().nullable(),
})

const DateTimeFieldInputBase = z.object({
  d: z.literal("datetime"),
  component: z.string(),
  name: z.string(),
  required: z.boolean(),
  default: z.string().nullable(),
})

const FileFieldInputBase = z.object({
  d: z.literal("file"),
  component: z.string(),
  name: z.string(),
  required: z.boolean(),
  default: z.any().nullable(),
})

const ForeignKeyFieldInputBase = z.object({
  d: z.literal("foreignkey"),
  component: z.string(),
  name: z.string(),
  required: z.boolean(),
  view_name: z.string(),
  default: z.object({ id: z.string(), text: z.string() }).nullable(),
})

export const CharFieldInputSchema = CharFieldInputBase
export const TextFieldInputSchema = TextFieldInputBase
export const IntegerFieldInputSchema = IntegerFieldInputBase
export const BooleanFieldInputSchema = BooleanFieldInputBase
export const DecimalFieldInputSchema = DecimalFieldInputBase
export const DateTimeFieldInputSchema = DateTimeFieldInputBase
export const FileFieldInputSchema = FileFieldInputBase
export const ForeignKeyFieldInputSchema = ForeignKeyFieldInputBase

export const InputSchema = z.discriminatedUnion("d", [
  CharFieldInputBase,
  TextFieldInputBase,
  IntegerFieldInputBase,
  BooleanFieldInputBase,
  DecimalFieldInputBase,
  DateTimeFieldInputBase,
  FileFieldInputBase,
  ForeignKeyFieldInputBase,
])

export type InputSchemaType = z.infer<typeof InputSchema>
export type CharFieldInput = z.infer<typeof CharFieldInputSchema>
export type TextFieldInput = z.infer<typeof TextFieldInputSchema>
export type IntegerFieldInput = z.infer<typeof IntegerFieldInputSchema>
export type BooleanFieldInput = z.infer<typeof BooleanFieldInputSchema>
export type DecimalFieldInput = z.infer<typeof DecimalFieldInputSchema>
export type DateTimeFieldInput = z.infer<typeof DateTimeFieldInputSchema>
export type FileFieldInput = z.infer<typeof FileFieldInputSchema>
export type ForeignKeyFieldInput = z.infer<typeof ForeignKeyFieldInputSchema>

// ------------------ Th/Content Schemas ---------------------

export const ThSchema = z.object({
  name: z.string(),
  component: z.string(),
})

export const ContentSchema = z.object({
  component: z.string(),
  value: z.any(),
})

export type ContentType = z.infer<typeof ContentSchema>

// ------------------ Td value schemas ---------------------
// Each Td component validates its content against these.

export const CharValueSchema = ContentSchema.extend({ value: z.string() })
export const TextValueSchema = ContentSchema.extend({ value: z.string() })
export const IntegerValueSchema = ContentSchema.extend({
  value: z.union([z.number(), z.string()]),
})
export const BooleanValueSchema = ContentSchema.extend({ value: z.boolean() })
export const DecimalValueSchema = ContentSchema.extend({ value: z.string() })
export const DateTimeValueSchema = ContentSchema.extend({ value: z.string() })
export const FileValueSchema = ContentSchema.extend({
  value: z.object({ filename: z.string(), download_url: z.string() }),
})
export const ForeignKeyValueSchema = ContentSchema.extend({
  value: z.object({ id: z.string(), title: z.string(), viewname: z.string() }),
})
export const NullValueSchema = ContentSchema.extend({ value: z.null() })

// Row Update column value schemas - wrapper types for complex values
const IntegerChoiceWrapperSchema = z.object({
  value: z.number().nullable(),
  value_title: nullableOptional(z.string()),
})

const CharChoiceWrapperSchema = z.object({
  value: z.string(),
  value_title: z.string(),
})

const ForeignKeyWrapperSchema = z.object({
  id: z.string().nullable(),
  title: nullableOptional(z.string()),
  url: nullableOptional(z.string()),
})

// Row Update column value schemas with old_value and new_value
export const RowBooleanColumnValueSchema = z.object({
  d: z.literal("boolean"),
  name: z.string(),
  old_value: nullableOptional(z.boolean()),
  new_value: nullableOptional(z.boolean()),
})

export const RowIntegerColumnValueSchema = z.object({
  d: z.literal("integer"),
  name: z.string(),
  old_value: nullableOptional(z.number()),
  new_value: nullableOptional(z.number()),
})

export const RowIntegerChoiceColumnValueSchema = z.object({
  d: z.literal("integer-choice"),
  name: z.string(),
  old_value: nullableOptional(IntegerChoiceWrapperSchema),
  new_value: nullableOptional(IntegerChoiceWrapperSchema),
})

export const RowCharColumnValueSchema = z.object({
  d: z.literal("char"),
  name: z.string(),
  old_value: nullableOptional(z.string()),
  new_value: nullableOptional(z.string()),
})

export const RowCharChoiceColumnValueSchema = z.object({
  d: z.literal("char_choice"),
  name: z.string(),
  old_value: nullableOptional(CharChoiceWrapperSchema),
  new_value: nullableOptional(CharChoiceWrapperSchema),
})

export const RowTextColumnValueSchema = z.object({
  d: z.literal("text"),
  name: z.string(),
  old_value: nullableOptional(z.string()),
  new_value: nullableOptional(z.string()),
})

export const RowDecimalColumnValueSchema = z.object({
  d: z.literal("decimal"),
  name: z.string(),
  old_value: nullableOptional(z.string()),
  new_value: nullableOptional(z.string()),
})

export const RowForeignKeyColumnValueSchema = z.object({
  d: z.literal("foreign_key"),
  name: z.string(),
  old_value: nullableOptional(ForeignKeyWrapperSchema),
  new_value: nullableOptional(ForeignKeyWrapperSchema),
})

export const RowDatetimeColumnValueSchema = z.object({
  d: z.literal("datetime"),
  name: z.string(),
  old_value: nullableOptional(z.string()),
  new_value: nullableOptional(z.string()),
})

export const RowFileColumnValueSchema = z.object({
  d: z.literal("file"),
  name: z.string(),
  old_value: nullableOptional(z.string()),
  new_value: nullableOptional(z.string()),
})

export const RowColumnValueSchema = z.union([
  RowBooleanColumnValueSchema,
  RowIntegerColumnValueSchema,
  RowIntegerChoiceColumnValueSchema,
  RowCharColumnValueSchema,
  RowCharChoiceColumnValueSchema,
  RowTextColumnValueSchema,
  RowDecimalColumnValueSchema,
  RowForeignKeyColumnValueSchema,
  RowDatetimeColumnValueSchema,
  RowFileColumnValueSchema,
])

export const RowUpdateResponseSchema = z.object({
  id: z.string(),
  action: z.enum(["created_row", "updated_row", "commented"]),
  created_at: z.string(),
  created_by: nullableOptional(UserSchema),
  column_values: nullableOptional(z.array(RowColumnValueSchema)),
  comment_content: nullableOptional(z.string()),
  comment_deleted_at: nullableOptional(z.string()),
  comment_deleted_by: nullableOptional(UserSchema),
  edited_by: nullableOptional(UserSchema),
  edited_at: nullableOptional(z.string()),
})

export const RowUpdateListResponseSchema = z.object({
  can_create_comment: z.boolean(),
  edit_comment_timeout: nullableOptional(z.number()),
  delete_comment_timeout: nullableOptional(z.number()),
  updates: z.array(RowUpdateResponseSchema),
})

export const RowDetailsProps = z.object({
  title: z.string(),
  viewname: z.string(),
  view_url: z.string(),
  id: z.string(),
  column_names: z.array(z.string()),
  fields: z.record(z.string(), ThSchema),
  cell_values: z.record(z.string(), ContentSchema.passthrough()),
  user: UserSchema.nullable(),
  can_edit: z.boolean(),
  can_delete: z.boolean(),
  slot_props: nullableOptional(z.record(z.string(), z.any())),
})

export const PaginationSchema = z.object({
  page: z.number(),
  per: z.number(),
})

export const BooleanValueFilterSchema = z.object({
  d: z.literal("bv"),
  value: z.boolean(),
})

export const IntegerComparisonFilterSchema = z.object({
  d: z.literal("icomp"),
  op: z.enum(["eq", "gt", "lt", "gte", "lte", "ne", "inc", "ex"]),
  number_1: z.number(),
  number_2: z.number().optional(),
})

export const IntegerChoiceFilterSchema = z.object({
  d: z.literal("ich"),
  mode: z.enum(["any", "none"]),
  options: z.array(z.number()),
})

export const IntegerNullFilterSchema = z.object({
  d: z.literal("null"),
  value: z.boolean(),
})

export const CharChoiceFilterSchema = z.object({
  d: z.literal("cc"),
  mode: z.enum(["any", "none"]),
  options: z.array(z.string()),
})

export const CharTextFilterSchema = z.object({
  d: z.literal("ct"),
  text: z.string(),
})

export const CharBlankFilterSchema = z.object({
  d: z.literal("cb"),
  value: z.boolean(),
})

// Custom Zod type for Decimal strings to preserve precision
const DecimalStringSchema = z
  .string()
  .refine((val) => /^-?\d+(\.\d+)?$/.test(val), {
    message: "Must be a valid decimal number",
  })
  .transform((val) => val) // Keep as string to preserve precision

// Type for decimal strings that represent actual decimal numbers
type DecimalString = string & { __decimalBrand?: never }

export const DecimalComparisonFilterSchema = z.object({
  d: z.literal("dcomp"),
  op: z.enum(["gt", "gte", "lt", "lte", "eq", "ne", "inc", "ex"]),
  number_1: DecimalStringSchema,
  number_2: DecimalStringSchema,
})

export const DatetimeComparisonFilterSchema = z.object({
  d: z.literal("dtcomp"),
  op: z.enum(["gt", "gte", "lt", "lte", "eq", "ne", "inc", "ex"]),
  datetime_1: z.string(),
  datetime_2: z.string(),
})

export const DecimalNullFilterSchema = z.object({
  d: z.literal("dnull"),
  value: z.boolean(),
})

export const DatetimeNullFilterSchema = z.object({
  d: z.literal("dtnull"),
  value: z.boolean(),
})

export const DatetimeRelativeFilterSchema = z.object({
  d: z.literal("dtrel"),
  direction: z.enum(["past", "next"]),
  unit: z.enum(["hours", "days", "months", "years"]),
  quantity: z.number(),
})

export const ForeignKeyChoiceFilterSchema = z.object({
  d: z.literal("fk"),
  mode: z.enum(["any", "none"]),
  options: z.array(z.string()),
})

export const ForeignKeyNullFilterSchema = z.object({
  d: z.literal("fknull"),
  value: z.boolean(),
})

export const RowUpdateFilterSchema = z
  .object({
    user_ids: z.array(z.string()).nullable(),
    actions: z
      .array(z.enum(["created_row", "updated_row", "commented"]))
      .nullable(),
    date_from: z.string().nullable(),
    date_to: z.string().nullable(),
  })
  .nullable()

export const FilterSchema = z.discriminatedUnion("d", [
  BooleanValueFilterSchema,
  IntegerComparisonFilterSchema,
  IntegerChoiceFilterSchema,
  IntegerNullFilterSchema,
  CharChoiceFilterSchema,
  CharTextFilterSchema,
  CharBlankFilterSchema,
  DecimalComparisonFilterSchema,
  DatetimeComparisonFilterSchema,
  DecimalNullFilterSchema,
  DatetimeNullFilterSchema,
  DatetimeRelativeFilterSchema,
  ForeignKeyChoiceFilterSchema,
  ForeignKeyNullFilterSchema,
])

export type BooleanValueFilter = z.infer<typeof BooleanValueFilterSchema>
export type IntegerComparisonFilter = z.infer<
  typeof IntegerComparisonFilterSchema
>
export type IntegerChoiceFilter = z.infer<typeof IntegerChoiceFilterSchema>
export type IntegerNullFilter = z.infer<typeof IntegerNullFilterSchema>
export type CharChoiceFilter = z.infer<typeof CharChoiceFilterSchema>
export type CharTextFilter = z.infer<typeof CharTextFilterSchema>
export type CharBlankFilter = z.infer<typeof CharBlankFilterSchema>
export type DecimalComparisonFilter = {
  d: "dcomp"
  op: "gt" | "gte" | "lt" | "lte" | "eq" | "ne" | "inc" | "ex"
  number_1: DecimalString
  number_2: DecimalString
}
export type DatetimeComparisonFilter = z.infer<
  typeof DatetimeComparisonFilterSchema
>
export type DatetimeRelativeFilter = z.infer<
  typeof DatetimeRelativeFilterSchema
>
export type DecimalNullFilter = z.infer<typeof DecimalNullFilterSchema>
export type DatetimeNullFilter = z.infer<typeof DatetimeNullFilterSchema>
export type ForeignKeyChoiceFilter = z.infer<
  typeof ForeignKeyChoiceFilterSchema
>
export type ForeignKeyNullFilter = z.infer<typeof ForeignKeyNullFilterSchema>

export const ListPageSchema = z.object({
  p: PaginationSchema,
  f: z.record(z.string(), FilterSchema).default({}),
  uf: RowUpdateFilterSchema.optional(),
})

export { ListPageSchemaWrapper } from "./ListPageSchemaWrapper"

export const ListRowsProps = z.object({
  viewname: z.string(),
  column_names: z.array(z.string()),
  columns: z.record(z.string(), ThSchema),
  columns_raw: z.record(z.string(), FieldSchema),
  rows: z.array(
    z
      .object({ id: z.string(), title: z.string() })
      .catchall(ContentSchema.passthrough()),
  ),
  list_page_schema: ListPageSchema,
  page: z.object({ total_pages: z.number(), total_count: z.number() }),
  user: UserSchema.nullable(),
  human_row_references: z
    .record(z.string(), z.record(z.string(), z.string()))
    .default({}),
  user_viewname: nullableOptional(z.string()),
  slot_props: nullableOptional(z.record(z.string(), z.any())),
})

export const CreateRowProps = z.object({
  viewname: z.string(),
  column_names: z.array(z.string()),
  fields: z.record(z.string(), InputSchema),
  user: UserSchema.nullable(),
})

export const UpdateRowProps = CreateRowProps.extend({
  row_id: z.string(),
})

const SuccessResponseSchema = z.object({
  d: z.literal("success"),
  id: z.string(),
})

const ValidationErrorResponseSchema = z.object({
  d: z.literal("validation_error"),
  errors: z.record(z.string(), z.string()),
  top_level_error: z.string().nullable(),
})

export const RowFormResponseSchema = z.discriminatedUnion("d", [
  SuccessResponseSchema,
  ValidationErrorResponseSchema,
])

export const SearchRowsResponseSchema = z.object({
  rows: z.array(z.object({ id: z.string(), title: z.string() })),
})

export const ArticleTagItemSchema = z.object({
  name: z.string(),
  color: z.string(),
})

export const ArticleListItemSchema = z.object({
  public_id: z.string(),
  title: z.string(),
  excerpt: z.string(),
  cover_image_url: z.string().nullable(),
  tags: z.array(ArticleTagItemSchema),
  author: UserSchema,
  published_at: z.string().nullable(),
})

export const ArticleListPaginationSchema = z.object({
  page: z.number(),
  total_pages: z.number(),
  total_count: z.number(),
})

export const ArticleListFiltersSchema = z.object({
  author: z.array(z.number()),
  tag: z.array(z.string()),
  unpublished: z.boolean(),
  page: z.number(),
  sort_by: z
    .enum(["published_at", "latest_comment"])
    .optional()
    .default("published_at"),
})

export const ArticleListPropsSchema = z.object({
  path_prefix: z.string(),
  user: UserSchema.nullable(),
  is_editor: z.boolean(),
  articles: z.array(ArticleListItemSchema),
  pagination: ArticleListPaginationSchema,
  filters: ArticleListFiltersSchema,
  selected_authors: z.array(UserSchema),
  selected_tags: z.array(ArticleTagItemSchema),
})

export const ArticleDetailsItemSchema = z.object({
  public_id: z.string(),
  title: z.string(),
  content: z.string(),
  published_at: z.string().nullable(),
  tags: z.array(ArticleTagItemSchema),
  author: UserSchema,
  is_commenting_enabled: z.boolean().optional().default(true),
})

export const MediaImageItemSchema = z.object({
  uuid_id: z.string(),
  size: z.number(),
  image_url: z.string(),
})

export const MediaSummarySchema = z.object({
  total_bytes: z.number(),
  quota_bytes: z.number(),
  images: z.array(MediaImageItemSchema),
})

export const ArticleCommentItemSchema = z.object({
  public_id: z.string(),
  content: z.string(),
  commented_by: UserSchema,
  commented_at: z.string(),
  updated_at: z.string().nullable(),
  is_deleted: z.literal(false),
})

export const DeletedArticleCommentItemSchema = z.object({
  public_id: z.string(),
  commented_by: UserSchema,
  commented_at: z.string(),
  is_deleted: z.literal(true),
})

export const ArticleCommentsResponseSchema = z.object({
  comments: z.array(
    z.discriminatedUnion("is_deleted", [
      ArticleCommentItemSchema,
      DeletedArticleCommentItemSchema,
    ]),
  ),
  can_comment: z.boolean(),
  can_delete_any: z.boolean(),
  user_id: z.number().nullable(),
})

export const ArticleDetailsPropsSchema = z.object({
  path_prefix: z.string(),
  user: UserSchema.nullable(),
  is_editor: z.boolean(),
  article: ArticleDetailsItemSchema,
  media_summary: MediaSummarySchema.nullable(),
  can_edit: z.boolean(),
  can_delete: z.boolean(),
  cover_image_url: z.string().nullable().optional(),
  history_count: z.number(),
  is_commenting_enabled: z.boolean().optional().default(true),
  is_subscribed: z.boolean().optional().default(false),
})

export const ArticleCreatePropsSchema = z.object({
  path_prefix: z.string(),
  user: UserSchema.nullable(),
  is_editor: z.boolean(),
  article: z.null(),
  media_summary: z.null(),
})

export const ArticleEditPropsSchema = z.object({
  path_prefix: z.string(),
  user: UserSchema.nullable(),
  is_editor: z.boolean(),
  article: ArticleDetailsItemSchema,
  media_summary: MediaSummarySchema,
})

export const ArticleTagWithCountSchema = z.object({
  name: z.string(),
  color: z.string(),
  article_count: z.number(),
})

export const ArticleTagManagementPropsSchema = z.object({
  path_prefix: z.string(),
  user: UserSchema.nullable(),
  is_editor: z.boolean(),
  tags: z.array(ArticleTagWithCountSchema),
})

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
  id: z.number(),
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

export type SearchRowsResponse = z.infer<typeof SearchRowsResponseSchema>

// TypeScript interfaces
export type CharField = z.infer<typeof CharFieldSchema>
export type TextField = z.infer<typeof TextFieldSchema>
export type IntegerField = z.infer<typeof IntegerFieldSchema>
export type BooleanField = z.infer<typeof BooleanFieldSchema>
export type DecimalField = z.infer<typeof DecimalFieldSchema>
export type DateTimeField = z.infer<typeof DateTimeFieldSchema>
export type FileField = z.infer<typeof FileFieldSchema>
export type ForeignKeyField = z.infer<typeof ForeignKeyFieldSchema>
export type Field = z.infer<typeof FieldSchema>
export type InputField = z.infer<typeof InputSchema>
export type RowDetailsProps = z.infer<typeof RowDetailsProps>
export type ListRowsProps = z.infer<typeof ListRowsProps>
export type CreateRowProps = z.infer<typeof CreateRowProps>
export type UpdateRowProps = z.infer<typeof UpdateRowProps>
export type RowFormResponse = z.infer<typeof RowFormResponseSchema>

export type FileFieldValue =
  | null
  | { filename: string; download_url: string }
  | File

export type ForeignKeyFieldValue = null | { id: string; text: string }

export type FieldValue =
  | string
  | number
  | boolean
  | FileFieldValue
  | ForeignKeyFieldValue
  | Date
  | File
  | null

export type RowUpdateFilter = z.infer<typeof RowUpdateFilterSchema>

export const ArticleHistoryTagItemSchema = z.object({
  name: z.string(),
  color: z.string(),
})

const StringChangeSchema = z.object({ old: z.string(), new: z.string() })
const NullableDateChangeSchema = z.object({
  old: z.string().nullable(),
  new: z.string().nullable(),
})
const TagListChangeSchema = z.object({
  old: z.array(ArticleHistoryTagItemSchema),
  new: z.array(ArticleHistoryTagItemSchema),
})
const AuthorChangeSchema = z.object({
  old: UserSchema,
  new: UserSchema,
})
const ArticleHistoryChangesSchema = z.object({
  title: StringChangeSchema.nullish(),
  public_id: StringChangeSchema.nullish(),
  content: StringChangeSchema.nullish(),
  tags: TagListChangeSchema.nullish(),
  author: AuthorChangeSchema.nullish(),
  published_date: NullableDateChangeSchema.nullish(),
})

export const ArticleHistoryEntrySchema = z.object({
  id: z.number(),
  action: z.enum(["created", "edited", "deleted"]),
  time: z.string(),
  changes: ArticleHistoryChangesSchema,
})

export const ArticleHistoryPropsSchema = z.object({
  path_prefix: z.string(),
  user: UserSchema.nullable(),
  is_editor: z.boolean(),
  article_public_id: z.string(),
  article_title: z.string(),
  entries: z.array(ArticleHistoryEntrySchema),
})

export type ArticleTagItem = z.infer<typeof ArticleTagItemSchema>
export type ArticleUserProfile = z.infer<typeof UserSchema>
export type ArticleTagWithCount = z.infer<typeof ArticleTagWithCountSchema>

export interface ArticleFormData {
  title: string
  publicId: string
  content: string
  selectedTags: ArticleTagItem[]
  isCommentingEnabled: boolean
  isPublished: boolean
}
