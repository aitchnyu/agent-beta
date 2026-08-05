<script setup lang="ts">
import { computed } from "vue"
import { Link, router } from "@inertiajs/vue3"
import BackToTopLink from "../components/BackToTopLink.vue"
import Layout from "../components/Layout.vue"
import RowCell from "../components/RowCell.vue"
import { ModelRowsPropsSchema } from "../schemas"
import { rowDetailUrl, rowListUrl } from "../utils/urls"

const props = defineProps<{ props: object }>()

const p = ModelRowsPropsSchema.parse(props.props)

// per_page selector (25/50/100) + sort (id/-id for every model;
// last_updated_at/-last_updated_at only for models with that column).
const PER_PAGE_OPTIONS = [25, 50, 100]
// id/-id apply to every model; last_updated_at/-last_updated_at only to models
// that carry that column (BaseModel subclasses).
const SORT_OPTIONS = [
  { value: "-id", label: "Newest id" },
  { value: "id", label: "Oldest id" },
  ...(p.columns.some((c) => c.name === "last_updated_at")
    ? [
        { value: "-last_updated_at", label: "Recently updated" },
        { value: "last_updated_at", label: "First updated" },
      ]
    : []),
]

const modelsHref = "/manage/models"

function applyFilters(perPage: number, sort: string) {
  // Changing the page size or sort order starts from page 1.
  router.visit(rowListUrl(p.model_name, { page: 1, per_page: perPage, sort }))
}

function onPerPageChange(event: Event) {
  applyFilters(
    Number((event.target as HTMLSelectElement).value),
    p.filters.sort,
  )
}

function onSortChange(event: Event) {
  applyFilters(p.filters.per_page, (event.target as HTMLSelectElement).value)
}

const prevHref = computed(() => {
  if (p.pagination.page <= 1) return null
  return rowListUrl(p.model_name, {
    page: p.pagination.page - 1,
    per_page: p.filters.per_page,
    sort: p.filters.sort,
  })
})

const nextHref = computed(() => {
  if (p.pagination.page >= p.pagination.total_pages) return null
  return rowListUrl(p.model_name, {
    page: p.pagination.page + 1,
    per_page: p.filters.per_page,
    sort: p.filters.sort,
  })
})
</script>

<template>
  <Layout>
    <div class="container manage-modelrows-page">
      <h1>{{ p.model_name }}</h1>
      <p class="text-muted">
        <Link href="/manage/models">Models</Link>
      </p>
      <div
        class="d-flex align-items-center gap-3 mb-3 manage-modelrows-controls"
      >
        <label class="d-flex align-items-center gap-1 mb-0">
          Per page
          <select
            class="form-select form-select-sm d-inline-block w-auto"
            :value="p.filters.per_page"
            @change="onPerPageChange"
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
            @change="onSortChange"
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
      <table class="table table-sm align-middle manage-modelrows-table">
        <thead>
          <tr>
            <th scope="col" class="manage-row-link-col"></th>
            <th v-for="col in p.columns" :key="col.name" scope="col">
              {{ col.name }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in p.rows" :key="row.public_id ?? index">
            <td class="manage-row-link-col">
              <Link
                v-if="row.public_id"
                class="manage-row-link"
                :href="rowDetailUrl(p.model_name, row.public_id)"
                >&rarr;</Link
              >
            </td>
            <td v-for="col in p.columns" :key="col.name">
              <RowCell :col="col" :value="row.values[col.name]" />
            </td>
          </tr>
          <tr v-if="p.rows.length === 0">
            <td
              :colspan="p.columns.length + 1"
              class="text-center text-muted py-4"
            >
              No rows.
            </td>
          </tr>
        </tbody>
      </table>

      <div class="d-flex align-items-center manage-modelrows-pagination">
        <Link
          v-if="prevHref"
          class="btn btn-sm btn-outline-secondary me-2 manage-prev-link"
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
          class="btn btn-sm btn-outline-secondary me-2 manage-next-link"
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

      <BackToTopLink :href="modelsHref">Back to models</BackToTopLink>
    </div>
  </Layout>
</template>
