<script setup lang="ts">
import { computed } from "vue"
import { Link, router } from "@inertiajs/vue3"
import BackToTopLink from "../components/BackToTopLink.vue"
import Layout from "../components/Layout.vue"
import RowCell from "../components/RowCell.vue"
import { RowListPropsSchema, type RowListColumnDef } from "../schemas"
import { formatDateTime } from "../utils/time"
import { rowDetailUrl, rowListUrl } from "../utils/urls"

const props = defineProps<{ props: object }>()

const p = RowListPropsSchema.parse(props.props)

// per_page / sort selectors (mirrors backend _ALLOWED_SORTS + 25/50/100).
const PER_PAGE_OPTIONS = [25, 50, 100]
const SORT_OPTIONS = [
  { value: "created_at", label: "Created" },
  { value: "edited_at", label: "Edited" },
]

const manageHref = computed(
  () => `/apps/a/${p.collection_name}/${p.app_name}/manage`,
)

const createdByCol: RowListColumnDef = {
  name: "created_by",
  type: "user",
  has_choices: false,
  fk_target: null,
}

function applyFilters(perPage: number, sort: string) {
  // Changing the page size or sort order starts from page 1.
  router.visit(
    rowListUrl(p.collection_name, p.app_name, p.table_name, {
      page: 1,
      per_page: perPage,
      sort,
    }),
  )
}

const prevHref = computed(() => {
  if (p.pagination.page <= 1) return null
  return rowListUrl(p.collection_name, p.app_name, p.table_name, {
    page: p.pagination.page - 1,
    per_page: p.filters.per_page,
    sort: p.filters.sort,
  })
})

const nextHref = computed(() => {
  if (p.pagination.page >= p.pagination.total_pages) return null
  return rowListUrl(p.collection_name, p.app_name, p.table_name, {
    page: p.pagination.page + 1,
    per_page: p.filters.per_page,
    sort: p.filters.sort,
  })
})
</script>

<template>
  <Layout>
    <div class="container apps-tablerows-page">
      <h1>{{ p.table_name }}</h1>
      <p class="text-muted">
        <Link href="/apps/collections">Collections</Link> /
        <Link :href="`/apps/a/${p.collection_name}/list`">{{
          p.collection_name
        }}</Link>
        /
        <Link :href="manageHref">{{ p.app_name }}</Link>
      </p>
      <div class="d-flex align-items-center gap-3 mb-3 apps-tablerows-controls">
        <label class="d-flex align-items-center gap-1 mb-0">
          Per page
          <select
            class="form-select form-select-sm d-inline-block w-auto"
            :value="p.filters.per_page"
            @change="
              applyFilters(
                Number(($event.target as HTMLSelectElement).value),
                p.filters.sort,
              )
            "
          >
            <option v-for="n in PER_PAGE_OPTIONS" :key="n" :value="n">
              {{ n }}
            </option>
          </select>
        </label>
        <label class="d-flex align-items-center gap-1 mb-0">
          Sort
          <select
            class="form-select form-select-sm d-inline-block w-auto"
            :value="p.filters.sort"
            @change="
              applyFilters(
                p.filters.per_page,
                ($event.target as HTMLSelectElement).value,
              )
            "
          >
            <option
              v-for="opt in SORT_OPTIONS"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </label>
      </div>
      <table class="table table-sm align-middle apps-tablerows-table">
        <thead>
          <tr>
            <th scope="col" class="apps-row-link-col"></th>
            <th v-for="col in p.columns" :key="col.name" scope="col">
              {{ col.name }}
            </th>
            <th scope="col">Created by</th>
            <th scope="col">Created at</th>
            <th scope="col">Edited at</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in p.rows" :key="row.public_id">
            <td class="apps-row-link-col">
              <Link
                class="apps-row-link"
                :href="
                  rowDetailUrl(
                    p.collection_name,
                    p.app_name,
                    p.table_name,
                    row.public_id,
                  )
                "
                >&rarr;</Link
              >
            </td>
            <td v-for="col in p.columns" :key="col.name">
              <RowCell :col="col" :value="row.values[col.name]" />
            </td>
            <td>
              <RowCell :col="createdByCol" :value="row.created_by" />
            </td>
            <td>{{ formatDateTime(row.created_at) }}</td>
            <td>{{ formatDateTime(row.edited_at) }}</td>
          </tr>
          <tr v-if="p.rows.length === 0">
            <td
              :colspan="p.columns.length + 4"
              class="text-center text-muted py-4"
            >
              No rows.
            </td>
          </tr>
        </tbody>
      </table>

      <div class="d-flex align-items-center apps-tablerows-pagination">
        <Link
          v-if="prevHref"
          class="btn btn-sm btn-outline-secondary me-2 apps-prev-link"
          :href="prevHref"
          >Prev</Link
        >
        <span v-else class="btn btn-sm btn-outline-secondary disabled me-2"
          >Prev</span
        >
        <span class="mx-2"
          >Page {{ p.pagination.page }} of {{ p.pagination.total_pages }}</span
        >
        <Link
          v-if="nextHref"
          class="btn btn-sm btn-outline-secondary me-2 apps-next-link"
          :href="nextHref"
          >Next</Link
        >
        <span v-else class="btn btn-sm btn-outline-secondary disabled me-2"
          >Next</span
        >
        <span class="text-muted ms-2"
          >{{ p.pagination.total_count }} total</span
        >
      </div>

      <BackToTopLink :href="manageHref">Back to {{ p.app_name }}</BackToTopLink>
    </div>
  </Layout>
</template>
