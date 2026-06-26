<script setup lang="ts">
import { Link, router } from "@inertiajs/vue3"
import { computed, ref } from "vue"
import { rowDetailsUrl } from "../utils/urls"
import Layout from "./Layout.vue"
import SearchHeader from "./SearchHeader.vue"
import { pushStartEdit } from "../utils/startEdit"
import {
  ListRowsProps,
  ListPageSchemaWrapper,
  type BooleanField,
  type IntegerField,
  type CharField,
  type TextField,
  type DecimalField,
  type DateTimeField,
  type ForeignKeyField,
  type BooleanValueFilter,
  type IntegerComparisonFilter,
  type IntegerChoiceFilter,
  type IntegerNullFilter,
  type CharChoiceFilter,
  type CharTextFilter,
  type CharBlankFilter,
  type DecimalComparisonFilter,
  type DecimalNullFilter,
  type DatetimeComparisonFilter,
  type DatetimeNullFilter,
  type ForeignKeyChoiceFilter,
  type ForeignKeyNullFilter,
  type RowUpdateFilter,
} from "../schemas"

import BooleanFilter from "./filters/BooleanFilter.vue"
import IntegerChoiceFilterComponent from "./filters/IntegerChoiceFilter.vue"
import IntegerCompareFilterComponent from "./filters/IntegerCompareFilter.vue"
import CharChoiceFilterComponent from "./filters/CharChoiceFilter.vue"
import CharTextFilterComponent from "./filters/CharTextFilter.vue"
import DecimalFilter from "./filters/DecimalFilter.vue"
import DatetimeFilter from "./filters/DatetimeFilter.vue"
import ForeignKeyFilter from "./filters/ForeignKeyFilter.vue"
import RowUpdateFilterComponent from "./filters/RowUpdateFilter.vue"

import { getTdComponent } from "../utils/tdComponents"

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Inertia props are untyped
const { props: rawProps } = defineProps<{ props: Record<string, any> }>()

console.log("props", rawProps)
const p = ListRowsProps.parse(rawProps)

const schema = new ListPageSchemaWrapper(
  p.viewname,
  p.list_page_schema,
  (url) => router.visit(url),
  rawProps.list_page_schema,
)

const currentPage = ref(p.list_page_schema.p.page)

const allPages = computed(() => {
  return Array.from({ length: p.page.total_pages }, (_, i) => i + 1)
})

const firstPage = schema.generatePage(1)

const prevUrl = computed(() => {
  const prevPage = p.list_page_schema.p.page - 1
  return prevPage >= 1 ? schema.generatePage(prevPage) : null
})

const nextUrl = computed(() => {
  const nextPage = p.list_page_schema.p.page + 1
  return nextPage <= p.page.total_pages ? schema.generatePage(nextPage) : null
})

function getBooleanFilter(name: string): BooleanValueFilter | undefined {
  return p.list_page_schema.f[name] as BooleanValueFilter | undefined
}

function getIntegerChoiceFilter(
  name: string,
): IntegerChoiceFilter | IntegerNullFilter | undefined {
  return p.list_page_schema.f[name] as
    | IntegerChoiceFilter
    | IntegerNullFilter
    | undefined
}

function getIntegerCompareFilter(
  name: string,
): IntegerComparisonFilter | IntegerNullFilter | undefined {
  return p.list_page_schema.f[name] as
    | IntegerComparisonFilter
    | IntegerNullFilter
    | undefined
}

function getCharChoiceFilter(
  name: string,
): CharChoiceFilter | CharBlankFilter | undefined {
  return p.list_page_schema.f[name] as
    | CharChoiceFilter
    | CharBlankFilter
    | undefined
}

function getCharTextFilter(
  name: string,
): CharTextFilter | CharBlankFilter | undefined {
  return p.list_page_schema.f[name] as
    | CharTextFilter
    | CharBlankFilter
    | undefined
}

function getDecimalFilter(
  name: string,
): DecimalComparisonFilter | DecimalNullFilter | undefined {
  return p.list_page_schema.f[name] as
    | DecimalComparisonFilter
    | DecimalNullFilter
    | undefined
}

function getDatetimeFilter(
  name: string,
): DatetimeComparisonFilter | DatetimeNullFilter | undefined {
  return p.list_page_schema.f[name] as
    | DatetimeComparisonFilter
    | DatetimeNullFilter
    | undefined
}

function getForeignKeyFilter(
  name: string,
): ForeignKeyChoiceFilter | ForeignKeyNullFilter | undefined {
  return p.list_page_schema.f[name] as
    | ForeignKeyChoiceFilter
    | ForeignKeyNullFilter
    | undefined
}

function getRowUpdateFilter(): RowUpdateFilter | undefined {
  return p.list_page_schema.uf
}

function colClass(columnName: string): string {
  const raw = p.columns_raw[columnName]
  if (raw && "d" in raw) {
    return `col-${(raw as { d: string }).d}`
  }
  return ""
}

function navigateToEdit(rowId: string, columnName: string) {
  pushStartEdit(columnName)
  router.visit(`/tables/${p.viewname}/update-row/${rowId}`)
}
</script>

<template>
  <Layout :user="p.user">
    <h1>{{ p.viewname }}</h1>
    <Link
      :href="`/tables/${p.viewname}/create-row`"
      class="btn btn-primary mb-3"
    >
      New
    </Link>
    <div v-if="$slots['before-filters']" class="slot-before-filters">
      <slot name="before-filters"></slot>
    </div>
    <div class="filters mb-3">
      <template v-for="c in p.columns_raw" :key="c.name">
        <BooleanFilter
          v-if="c.d === 'boolean'"
          :column="c as BooleanField"
          :currentFilter="getBooleanFilter(c.name)"
          :wrapper="schema"
        />
        <IntegerChoiceFilterComponent
          v-else-if="c.d === 'integer' && (c as IntegerField).choices"
          :column="c as IntegerField"
          :currentFilter="getIntegerChoiceFilter(c.name)"
          :wrapper="schema"
        />
        <IntegerCompareFilterComponent
          v-else-if="c.d === 'integer' && !(c as IntegerField).choices"
          :column="c as IntegerField"
          :currentFilter="getIntegerCompareFilter(c.name)"
          :wrapper="schema"
        />
        <CharChoiceFilterComponent
          v-else-if="c.d === 'char' && (c as CharField).choices"
          :column="c as CharField"
          :currentFilter="getCharChoiceFilter(c.name)"
          :wrapper="schema"
        />
        <CharTextFilterComponent
          v-else-if="c.d === 'char' && !(c as CharField).choices"
          :column="c as CharField"
          :currentFilter="getCharTextFilter(c.name)"
          :wrapper="schema"
        />
        <CharTextFilterComponent
          v-else-if="c.d === 'text'"
          :column="c as TextField"
          :currentFilter="getCharTextFilter(c.name)"
          :wrapper="schema"
        />
        <DecimalFilter
          v-else-if="c.d === 'decimal'"
          :column="c as DecimalField"
          :currentFilter="getDecimalFilter(c.name)"
          :wrapper="schema"
        />
        <DatetimeFilter
          v-else-if="c.d === 'datetime'"
          :column="c as DateTimeField"
          :currentFilter="getDatetimeFilter(c.name)"
          :wrapper="schema"
        />
        <ForeignKeyFilter
          v-else-if="c.d === 'foreignkey'"
          :column="c as ForeignKeyField"
          :currentFilter="getForeignKeyFilter(c.name)"
          :wrapper="schema"
          :viewname="p.viewname"
          :humanRowReferences="p.human_row_references"
        />
      </template>
      <RowUpdateFilterComponent
        :currentFilter="getRowUpdateFilter()"
        :wrapper="schema"
        :humanRowReferences="p.human_row_references"
        :userViewname="p.user_viewname"
      />
      <slot name="extra-filters" :schema="schema"></slot>
    </div>
    <div v-if="$slots['after-filters']" class="slot-after-filters">
      <slot name="after-filters"></slot>
    </div>
    <div v-if="$slots['before-table']" class="slot-before-table">
      <slot name="before-table"></slot>
    </div>
    <div class="list-rows-table-wrapper">
      <table class="table list-rows-table">
        <thead>
          <tr>
            <SearchHeader :rows="p.rows" :viewname="p.viewname" />
            <th
              v-for="column in p.columns"
              :key="column.name"
              :class="colClass(column.name)"
            >
              {{ column.name }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in p.rows" :key="row.id" :class="`row-tr-${row.id}`">
            <td class="col-id">
              <Link
                :href="rowDetailsUrl(p.viewname, row.id)"
                target="_blank"
                class="row-title-link"
              >
                {{ row.title }}
              </Link>
            </td>
            <template v-for="column in p.columns" :key="column.name">
              <td
                :class="[`row-td-${column.name}`, colClass(column.name)]"
                @dblclick="navigateToEdit(row.id, column.name)"
              >
                <component
                  :is="getTdComponent(row[column.name]!)"
                  :content="row[column.name]!"
                />
              </td>
            </template>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="d-flex align-items-center pagination-stuff">
      <div class="pagination-page me-2">
        Page
        <select
          v-model="currentPage"
          @change="schema.navigateToPage(Number(currentPage))"
          class="form-select d-inline-block w-auto mx-1"
        >
          <option v-for="page in allPages" :key="page" :value="page">
            {{ page }}
          </option>
        </select>
        of {{ p.page.total_pages }}
      </div>
      <Link :href="firstPage" class="btn btn-outline-primary me-2">
        First
      </Link>
      <Link v-if="prevUrl" :href="prevUrl" class="btn btn-secondary me-2">
        Prev
      </Link>
      <Link v-if="nextUrl" :href="nextUrl" class="btn btn-secondary">
        Next
      </Link>
      <span class="muted-label ms-2">{{ p.page.total_count }} items total</span>
    </div>
    <div v-if="$slots['after-table']" class="slot-after-table">
      <slot name="after-table"></slot>
    </div>
  </Layout>
</template>
