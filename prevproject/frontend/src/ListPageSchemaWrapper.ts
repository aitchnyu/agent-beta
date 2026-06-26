// @ts-expect-error - rison package has no TypeScript definitions available
import Rison from "rison"
import cloneDeep from "lodash/cloneDeep"
import { type z } from "zod"
import { ListPageSchema } from "./schemas"
import { listRowsUrl } from "./utils/urls"

/**
 * Wraps parsed list-page state and raw schema props, providing navigate
 * methods that build rison-encoded URLs for Inertia visits.
 *
 * Each navigate method clones the raw schema, mutates filter_map (or a
 * custom key), resets pagination to page 1 (unless otherwise specified),
 * and calls the navigation callback with the generated URL.
 *
 * **Custom / generic**
 * - {@link navigateCustom} — set any key (e.g. ``diff`` in SlotDemo)
 * - {@link navigateUnsetFilter} — remove a filter_map entry
 *
 * **Pagination**
 * - {@link navigateToPage} — visit a specific page number
 * - {@link generatePage} — return URL for a page (no navigation)
 * - {@link firstPage} — URL of page 1
 *
 * **Boolean**
 * - {@link navigateBooleanValue}
 *
 * **Integer** (compare + choices + null)
 * - {@link navigateIntegerCompareValue}
 * - {@link navigateIntegerChoices}
 * - {@link navigateIntegerNullValue}
 *
 * **Char** (choices + text + blank)
 * - {@link navigateCharChoices}
 * - {@link navigateCharText}
 * - {@link navigateCharBlank}
 *
 * **Decimal** (compare + null)
 * - {@link navigateDecimalCompare}
 * - {@link navigateDecimalNull}
 *
 * **Datetime** (compare + null + relative)
 * - {@link navigateDatetimeCompare}
 * - {@link navigateDatetimeNull}
 * - {@link navigateDatetimeRelative}
 *
 * **ForeignKey** (choices + null)
 * - {@link navigateForeignKeyChoices}
 * - {@link navigateForeignKeyNull}
 *
 * **Row-update filter**
 * - {@link navigateRowUpdateFilter}
 * - {@link navigateUnsetRowUpdateFilter}
 */
export class ListPageSchemaWrapper {
  /* eslint-disable no-unused-vars -- TS parameter properties used as this._* */
  constructor(
    public _viewname: string,
    public _listPageSchema: z.infer<typeof ListPageSchema>,
    public _callback: (url: string) => void,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- raw props are untyped
    public _rawSchema: Record<string, any> = {},
  ) {}
  /* eslint-enable no-unused-vars */

  navigateCustom(key: string, value: unknown): void {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- raw schema mutation
    const raw = cloneDeep(this._rawSchema) as any
    if (value == null) {
      delete raw[key]
    } else {
      raw[key] = value
    }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateToPage(pageNumber: number): void {
    const raw = cloneDeep(this._rawSchema)
    this._callback(this.generateUrlFromRaw(raw, pageNumber))
  }

  generatePage(pageNumber: number): string {
    const raw = cloneDeep(this._rawSchema)
    return this.generateUrlFromRaw(raw, pageNumber)
  }

  get firstPage(): string {
    return this.generatePage(1)
  }

  private generateUrlFromRaw(
    schema: Record<string, any>, // eslint-disable-line @typescript-eslint/no-explicit-any -- raw schema is untyped
    pageNumber: number = 1,
  ): string {
    schema.p.page = pageNumber
    const schemaToEncode = { ...schema }
    for (const key of Object.keys(schemaToEncode)) {
      if (schemaToEncode[key] === null || schemaToEncode[key] === undefined) {
        delete schemaToEncode[key]
      }
    }
    const risonStr = Rison.encode(schemaToEncode)
    return listRowsUrl(this._viewname, risonStr)
  }

  navigateBooleanValue(column: string, value: boolean): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = { d: "bv", value }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateIntegerCompareValue(
    column: string,
    operator: "eq" | "gt" | "lt" | "gte" | "lte" | "ne" | "inc" | "ex",
    number1: number,
    number2?: number,
  ): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = {
      d: "icomp",
      op: operator,
      number_1: number1,
      number_2: number2,
    }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateIntegerChoices(
    column: string,
    mode: "any" | "none",
    options: number[],
  ): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = { d: "ich", mode, options }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateIntegerNullValue(column: string, value: boolean): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = { d: "null", value }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateCharChoices(
    column: string,
    mode: "any" | "none",
    options: string[],
  ): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = { d: "cc", mode, options }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateCharText(column: string, text: string): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = { d: "ct", text }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateCharBlank(column: string, value: boolean): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = { d: "cb", value }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateDecimalCompare(
    column: string,
    operator: "gt" | "gte" | "lt" | "lte" | "eq" | "ne" | "inc" | "ex",
    number1: string,
    number2: string,
  ): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = {
      d: "dcomp",
      op: operator,
      number_1: number1,
      number_2: number2,
    }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateDatetimeCompare(
    column: string,
    operator: "gt" | "gte" | "lt" | "lte" | "eq" | "ne" | "inc" | "ex",
    datetime1: string,
    datetime2: string,
  ): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = {
      d: "dtcomp",
      op: operator,
      datetime_1: datetime1,
      datetime_2: datetime2,
    }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateDecimalNull(column: string, value: boolean): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = { d: "dnull", value }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateDatetimeNull(column: string, value: boolean): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = { d: "dtnull", value }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateDatetimeRelative(
    column: string,
    direction: "past" | "next",
    unit: "hours" | "days" | "months" | "years",
    quantity: number,
  ): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = {
      d: "dtrel",
      direction,
      unit,
      quantity,
    }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateForeignKeyChoices(
    column: string,
    mode: "any" | "none",
    options: string[],
  ): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = { d: "fk", mode, options }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateForeignKeyNull(column: string, value: boolean): void {
    const raw = cloneDeep(this._rawSchema)
    raw.f[column] = { d: "fknull", value }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateUnsetFilter(column: string): void {
    const raw = cloneDeep(this._rawSchema)
    delete raw.f[column]
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateRowUpdateFilter(
    user_ids: string[] | null,
    actions: ("created_row" | "updated_row" | "commented")[] | null,
    date_from: string | null,
    date_to: string | null,
  ): void {
    const raw = cloneDeep(this._rawSchema)
    raw.uf = {
      user_ids,
      actions,
      date_from,
      date_to,
    }
    this._callback(this.generateUrlFromRaw(raw))
  }

  navigateUnsetRowUpdateFilter(): void {
    const raw = cloneDeep(this._rawSchema)
    delete raw.uf
    this._callback(this.generateUrlFromRaw(raw))
  }
}
