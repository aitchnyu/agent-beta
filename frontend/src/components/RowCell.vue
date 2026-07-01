<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
import { UserSchema, type RowListColumnDef } from "../schemas"
import { formatDateTime } from "../utils/time"

// Renders a single cell value for the row list/detail pages, keyed off the
// column's type: user cells link to the profile, datetime cells render in
// local time, boolean cells read Yes/No, everything else renders raw.
defineProps<{ col: RowListColumnDef; value: unknown }>()

function userOf(cell: unknown) {
  const parsed = UserSchema.nullable().safeParse(cell)
  return parsed.success ? parsed.data : null
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
  <template v-else-if="col.type === 'datetime'">{{
    formatDateTime(value as string | null | undefined)
  }}</template>
  <template v-else>{{ renderText(col, value) }}</template>
</template>
