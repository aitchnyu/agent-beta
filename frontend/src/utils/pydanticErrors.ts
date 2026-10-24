/**
 * The error-detail catalog for form validation.
 *
 * A 422 body entry ({"type", "msg", "ctx", "loc"}) becomes an ErrorDetail.
 * Pydantic's built-in types are all known here: they never show pydantic's
 * raw msg ("Input should be a valid integer" is not user copy) — each gets
 * a plain template instead, with ctx values interpolated. Any type that is
 * NOT a pydantic built-in is an endpoint-authored custom error and its msg
 * is trusted verbatim as user copy. Per-use copy overrides ride on
 * FieldError's message-for prop.
 */
import { z } from "zod"

/** An error whose plain-language presentation is part of the error itself.
 *
 *  `message` is the technical copy (console + client-errors log);
 *  `userTitle`/`userHtml` are what the toast shows — `userHtml` is
 *  sanitized to a safe tag subset at render time (see sweetalert.ts).
 */
export class UserVisibleError extends Error {
  readonly userTitle: string
  readonly userHtml: string

  constructor(message: string, userTitle: string, userHtml: string) {
    super(message)
    this.name = "UserVisibleError"
    this.userTitle = userTitle
    this.userHtml = userHtml
  }
}

/** One validation error, whatever raised it. */
export type ErrorDetail = {
  type: string
  msg: string
  ctx?: Record<string, unknown>
}

// Every pydantic (v2.13) built-in validation error type. The catalog
// mirrors the pinned pydantic version — recheck
// https://docs.pydantic.dev/latest/errors/validation_errors/ on upgrade.
const BUILTIN_TYPES = [
  "arguments_type",
  "assertion_error",
  "bool_parsing",
  "bool_type",
  "bytes_invalid_encoding",
  "bytes_too_long",
  "bytes_too_short",
  "bytes_type",
  "callable_type",
  "complex_str_parsing",
  "complex_type",
  "counter_type",
  "dataclass_exact_type",
  "dataclass_type",
  "date_from_datetime_inexact",
  "date_from_datetime_parsing",
  "date_future",
  "date_parsing",
  "date_past",
  "date_type",
  "datetime_from_date_parsing",
  "datetime_future",
  "datetime_object_invalid",
  "datetime_parsing",
  "datetime_past",
  "datetime_type",
  "decimal_max_digits",
  "decimal_max_places",
  "decimal_parsing",
  "decimal_type",
  "decimal_whole_digits",
  "default_factory_not_called",
  "deque_type",
  "dict_type",
  "ellipsis_error",
  "enum",
  "extra_forbidden",
  "finite_number",
  "float_parsing",
  "float_type",
  "fraction_parsing",
  "fraction_type",
  "frozen_dict_type",
  "frozen_field",
  "frozen_instance",
  "frozen_set_type",
  "get_attribute_error",
  "greater_than",
  "greater_than_equal",
  "int_from_float",
  "int_parsing",
  "int_parsing_size",
  "int_type",
  "invalid_key",
  "is_instance_of",
  "is_subclass_of",
  "iterable_type",
  "iteration_error",
  "json_invalid",
  "json_type",
  "less_than",
  "less_than_equal",
  "list_type",
  "literal_error",
  "mapping_type",
  "missing",
  "missing_argument",
  "missing_keyword_only_argument",
  "missing_positional_only_argument",
  "missing_sentinel_error",
  "model_attributes_type",
  "model_type",
  "multiple_argument_values",
  "multiple_of",
  "named_tuple_type",
  "needs_python_object",
  "no_such_attribute",
  "none_required",
  "ordered_dict_type",
  "recursion_loop",
  "set_item_not_hashable",
  "set_type",
  "string_not_ascii",
  "string_pattern_mismatch",
  "string_too_long",
  "string_too_short",
  "string_type",
  "string_unicode",
  "time_delta_parsing",
  "time_delta_type",
  "time_parsing",
  "time_type",
  "timezone_aware",
  "timezone_naive",
  "too_long",
  "too_short",
  "tuple_type",
  "unexpected_keyword_argument",
  "unexpected_positional_argument",
  "union_tag_invalid",
  "union_tag_not_found",
  "url_parsing",
  "url_scheme",
  "url_syntax_violation",
  "url_too_long",
  "url_type",
  "uuid_parsing",
  "uuid_type",
  "uuid_version",
  "value_error",
] as const

const BUILTIN_SET = new Set<string>(BUILTIN_TYPES)

/** Is this type one of pydantic's built-ins (i.e. not endpoint-authored)? */
export const isBuiltinErrorType = (type: string): boolean =>
  BUILTIN_SET.has(type)

/** ctx as the loose bag templates read from. */
type CtxBag = Record<string, unknown>

const num = (ctx: CtxBag, key: string): string => {
  const value = ctx[key]
  return typeof value === "number" ? String(value) : ""
}

/** Plain copy per built-in type — the only pydantic-side text we show. */
const BUILTIN_MESSAGES: Record<string, string | ((_: CtxBag) => string)> = {
  bool_parsing: "Pick yes or no",
  bool_type: "Pick yes or no",
  bytes_too_long: "That's too long",
  bytes_too_short: "That's too short",
  complex_str_parsing: "Enter a number",
  complex_type: "Enter a number",
  date_from_datetime_inexact: "Enter a date without a time",
  date_from_datetime_parsing: "Enter a date",
  date_future: "Enter a date in the future",
  date_parsing: "Enter a date",
  date_past: "Enter a date in the past",
  date_type: "Enter a date",
  datetime_from_date_parsing: "Enter a date and time",
  datetime_parsing: "Enter a date and time",
  datetime_type: "Enter a date and time",
  decimal_parsing: "Enter a number",
  decimal_type: "Enter a number",
  enum: "Pick one of the options",
  extra_forbidden: "This isn't accepted",
  finite_number: "Enter a number",
  float_parsing: "Enter a number",
  float_type: "Enter a number",
  fraction_parsing: "Enter a number",
  fraction_type: "Enter a number",
  greater_than: (ctx) => `Enter more than ${num(ctx, "gt")}`.trim(),
  greater_than_equal: (ctx) => `Enter ${num(ctx, "ge")} or more`.trim(),
  int_from_float: "Enter a number",
  int_parsing: "Enter a number",
  int_parsing_size: "Enter a smaller number",
  int_type: "Enter a number",
  less_than: (ctx) => `Enter less than ${num(ctx, "lt")}`.trim(),
  less_than_equal: (ctx) => `Enter ${num(ctx, "le")} or less`.trim(),
  literal_error: "Pick one of the options",
  missing: "This is required",
  multiple_of: "Pick a valid step",
  string_not_ascii: "Use plain characters only",
  string_pattern_mismatch: "Use the expected format",
  string_too_long: (ctx) =>
    `Keep it under ${num(ctx, "max_length")} characters`,
  string_too_short: (ctx) =>
    `Use at least ${num(ctx, "min_length")} characters`,
  string_type: "Enter some text",
  string_unicode: "Enter some text",
  time_delta_parsing: "Enter a duration",
  time_delta_type: "Enter a duration",
  time_parsing: "Enter a time",
  time_type: "Enter a time",
  timezone_aware: "Enter a time with a time zone",
  timezone_naive: "Enter a time without a time zone",
  too_long: (ctx) => `Keep it under ${num(ctx, "max_length")} items`,
  too_short: (ctx) => `Use at least ${num(ctx, "min_length")} items`,
  url_parsing: "Enter a valid web address",
  url_scheme: "Enter a valid web address",
  url_syntax_violation: "Enter a valid web address",
  url_too_long: "Enter a valid web address",
  url_type: "Enter a valid web address",
  uuid_parsing: "Enter a valid id",
  uuid_type: "Enter a valid id",
  uuid_version: "Enter a valid id",
  // pydantic's generic wrapper for plain ValueError — its raw msg is not
  // necessarily user copy, so it gets the generic line like every other
  // built-in without a template above.
  value_error: "Check this value",
}

/** The catalog's template hit for a detail, or null when there is none. */
export const tryMessageFor = (error: ErrorDetail): string | null => {
  const template = BUILTIN_MESSAGES[error.type]
  if (template === undefined) return null
  return typeof template === "string"
    ? template
    : template((error.ctx ?? {}) as CtxBag)
}

/** The user-visible line for one error detail (what FieldError renders). */
export const messageFor = (error: ErrorDetail): string => {
  const template = tryMessageFor(error)
  if (template !== null) return template
  // No template: pydantic built-ins fall back to generic copy (their raw
  // msg is never shown); custom errors are endpoint-authored — trust them.
  return isBuiltinErrorType(error.type) ? "Check this value" : error.msg
}

/** The loose envelope one 422 detail entry parses into. */
export const ErrorEntrySchema = z.object({
  type: z.string(),
  msg: z.string(),
  loc: z.array(z.union([z.string(), z.number()])).optional(),
  ctx: z.record(z.string(), z.unknown()).optional(),
})

export type ErrorEntry = z.infer<typeof ErrorEntrySchema>

/**
 * The ApiError body every djangoapp error handler writes (keys omitted
 * when unset — see djangoapp/ninja_api.py). A body msg is user copy.
 */
export const ApiErrorSchema = z.object({
  type: z.string().optional(),
  msg: z.string().optional(),
  ctx: z.record(z.string(), z.unknown()).optional(),
})

/** ninja's own HttpError body — a bare detail string is authored copy. */
export const DetailStringSchema = z.object({ detail: z.string() })

/** One segment of a pydantic error location: a field key or list index. */
export type LocSegment = string | number

/** The body shape ninja produces for schema validation failures (422). */
const ValidationBodySchema = z.object({ detail: z.array(ErrorEntrySchema) })

const detailOf = (entry: ErrorEntry): ErrorDetail => ({
  type: entry.type,
  msg: entry.msg,
  ...(entry.ctx !== undefined ? { ctx: entry.ctx } : {}),
})

/**
 * A ninja 422 validation failure, returned (never thrown) by the ninja*
 * helpers in utils/http.ts. Forms keep the scoped child and render fields
 * by path (errorAtPath); bind every field the payload validates.
 */
export class NinjaError extends Error {
  private readonly entries: readonly ErrorEntry[]
  /** The loc prefix this error's paths are relative to. */
  private readonly prefix: readonly LocSegment[]

  constructor(
    entries: readonly ErrorEntry[] = [],
    prefix: readonly LocSegment[] = [],
  ) {
    super("Validation failed")
    this.name = "NinjaError"
    this.entries = entries
    this.prefix = prefix
  }

  /**
   * The error at `path` (relative to this error's scope), or null.
   * An exact-loc entry wins; otherwise the first entry at-or-under the
   * path answers — a bad list item answers errorAtPath(["weekdays"]).
   */
  errorAtPath(path: readonly LocSegment[]): ErrorDetail | null {
    const scope = [...this.prefix, ...path]
    let under: ErrorEntry | null = null
    for (const entry of this.entries) {
      const loc = entry.loc ?? []
      if (loc.length < scope.length) continue
      if (!scope.every((segment, i) => loc[i] === segment)) continue
      if (loc.length === scope.length) return detailOf(entry)
      if (under === null) under = entry
    }
    return under === null ? null : detailOf(under)
  }

  /** A child scoped under `path` — same errors, calls without the prefix. */
  childForPath(path: readonly LocSegment[]): NinjaError {
    return new NinjaError(this.entries, [...this.prefix, ...path])
  }
}

/**
 * Build a NinjaError from a 422 body — ky hands these over already
 * parsed (err.data) — or null when the body isn't the ninja validation
 * shape.
 */
export const ninjaErrorFrom = (data: unknown): NinjaError | null => {
  const parsed = ValidationBodySchema.safeParse(data)
  return parsed.success ? new NinjaError(parsed.data.detail) : null
}

// MAINTAIN-CONSISTENCY pydantic-errors — the catalog mirrors the pinned
// pydantic version; ourapp/views raise the custom types templated here
// (see pyproject.toml, steer.md § Forms & validation errors).
