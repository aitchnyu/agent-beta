<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import {
  FkCellValueSchema,
  UserSchema,
  type RowListColumnDef,
} from "../schemas"
import { rowDetailUrl } from "../utils/urls"
import { formatDateTime } from "../utils/time"

// Renders a single cell value for the row list/detail pages, keyed off the
// column's type: user cells link to the profile, foreign_key cells link to the
// referenced row's detail page, datetime cells render in local time, boolean
// cells read Yes/No, everything else renders raw.
defineProps<{ col: RowListColumnDef; value: unknown }>()

function userOf(cell: unknown) {
  const parsed = UserSchema.nullable().safeParse(cell)
  return parsed.success ? parsed.data : null
}

// Resolve a foreign_key cell to its {public_id} (or null when unset).
function fkOf(cell: unknown) {
  const parsed = FkCellValueSchema.nullable().safeParse(cell)
  return parsed.success ? parsed.data : null
}

// The referenced row's detail URL, using the column's fk_target table (or
// null when the cell is unset or the target is missing).
function fkHref(col: RowListColumnDef, cell: unknown): string | null {
  const fk = fkOf(cell)
  const target = col.fk_target
  if (!fk || !target) return null
  return rowDetailUrl(
    target.collection_name,
    target.app_name,
    target.table_name,
    fk.public_id,
  )
}

function renderText(col: RowListColumnDef, cell: unknown): string {
  if (cell === null || cell === undefined) return "—"
  if (col.type === "boolean") return cell ? "Yes" : "No"
  return String(cell)
}
</script>

<template>
  <Link
    v-if="col.type === 'user' && userOf(value)"
    :href="`/users/id/${userOf(value)?.public_id}`"
    >{{ userOf(value)?.title }}</Link
  >
  <Link
    v-else-if="col.type === 'foreign_key' && fkHref(col, value)"
    :href="fkHref(col, value) ?? ''"
    >{{ fkOf(value)?.public_id }}</Link
  >
  <template v-else-if="col.type === 'datetime'">{{
    formatDateTime(value as string | null | undefined)
  }}</template>
  <template v-else>{{ renderText(col, value) }}</template>
</template>
