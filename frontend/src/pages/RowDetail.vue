<script setup lang="ts">
import { computed } from "vue"
import { Link } from "@inertiajs/vue3"
import BackToTopLink from "../components/BackToTopLink.vue"
import PageTitle from "../components/PageTitle.vue"
import RowCell from "../components/RowCell.vue"
import {
  RowDetailPropsSchema,
  UpdateLogEntryItemSchema,
  type UpdateLogEntryItem,
} from "../schemas"
import { formatDateTime } from "../utils/time"
import { rowListUrl } from "../utils/urls"

// `props` is the row's core (model_name/columns/values); `logs` is a separate
// deferred Inertia prop — undefined on first paint, then fetched automatically
// by the Inertia v3 client from the page's deferredProps metadata (no
// hand-rolled reload), landing via a partial reload (only: ["logs"]).
const props = defineProps<{
  props: object
  logs?: UpdateLogEntryItem[] | null
}>()

const p = computed(() => RowDetailPropsSchema.parse(props.props))
const listHref = computed(() => rowListUrl(p.value.model_name))

// logs is undefined/null before the partial lands; expose a loaded flag + an
// always-array view so the template narrows cleanly. The payload is parsed
// (every server payload is) so a shape drift fails loud at the boundary, not
// mid-template render.
const logsLoaded = computed(
  () => props.logs !== undefined && props.logs !== null,
)
const logs = computed(
  () =>
    UpdateLogEntryItemSchema.array().nullable().optional().parse(props.logs) ??
    [],
)

function changeKeys(e: UpdateLogEntryItem): string[] {
  return Array.from(
    new Set([...Object.keys(e.old_values), ...Object.keys(e.new_values)]),
  )
}

// Render an audit value: an FK target shows its name; scalars stringify;
// missing (the side that has no value for this field) renders as "—".
function formatLogValue(v: unknown): string {
  if (v == null) return "—"
  if (typeof v === "object") {
    const o = v as { name?: string; id?: string }
    return o.name ?? o.id ?? JSON.stringify(v)
  }
  return String(v)
}
</script>

<template>
  <PageTitle :value="p.model_name + ' / ' + p.public_id" />
  <div class="container manage-rowdetail-page">
    <h1>{{ p.model_name }} / {{ p.public_id }}</h1>
    <p class="text-muted">
      <Link :href="listHref">Back to {{ p.model_name }} list</Link>
    </p>

    <table class="table table-sm align-middle manage-rowdetail-table">
      <tbody>
        <tr v-for="col in p.columns" :key="col.name">
          <th scope="row">{{ col.name }}</th>
          <td>
            <RowCell :col="col" :value="p.values[col.name]" />
          </td>
        </tr>
      </tbody>
    </table>

    <section class="manage-rowdetail-logs">
      <h2>History</h2>
      <p v-if="!logsLoaded" class="text-muted">Loading history…</p>
      <p v-else-if="logs.length === 0" class="text-muted">No history.</p>
      <ul v-else>
        <li
          v-for="e in logs"
          :key="e.id"
          class="update-log-entry"
          :class="`action-${e.action}`"
        >
          <span class="update-log-action">{{ e.action }}</span>
          by
          <Link
            v-if="e.performed_by"
            :href="`/users/id/${e.performed_by.public_id}`"
            >{{ e.performed_by.title }}</Link
          >
          <span v-else>—</span>
          <span class="text-muted">{{ formatDateTime(e.performed_at) }}</span>
          <ul>
            <li
              v-for="key in changeKeys(e)"
              :key="key"
              class="update-log-change"
            >
              <code>{{ key }}</code
              >:
              <span class="update-log-old">{{
                formatLogValue(e.old_values[key])
              }}</span>
              →
              <span class="update-log-new">{{
                formatLogValue(e.new_values[key])
              }}</span>
            </li>
          </ul>
        </li>
      </ul>
    </section>

    <BackToTopLink :href="listHref">Back to {{ p.model_name }}</BackToTopLink>
  </div>
</template>
