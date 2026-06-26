<script setup lang="ts">
import { ref, computed, watch } from "vue"
import axios from "axios"
import FilterWrapper from "./FilterWrapper.vue"
import FilterBox from "./FilterBox.vue"
import EmptyFilter from "./EmptyFilter.vue"
import Multiselect from "vue-multiselect"
import { SearchRowsResponseSchema } from "../../schemas"
import { showErrorToast } from "../../utils/sweetalert"
import type {
  ForeignKeyField,
  ForeignKeyChoiceFilter,
  ForeignKeyNullFilter,
  ListPageSchemaWrapper,
} from "../../schemas"

interface MultiselectOption {
  id: string
  text: string
}

interface Props {
  column: ForeignKeyField
  currentFilter: ForeignKeyChoiceFilter | ForeignKeyNullFilter | undefined
  wrapper: ListPageSchemaWrapper
  viewname: string
  humanRowReferences: Record<string, Record<string, string>>
}

const props = defineProps<Props>()

const selectedOptions = ref<MultiselectOption[]>([])
const options = ref<MultiselectOption[]>([])
const isLoading = ref(false)

const searchRelatedRows = async (
  query: string,
): Promise<MultiselectOption[]> => {
  if (query.length < 2) {
    options.value = []
    return []
  }

  try {
    isLoading.value = true
    const response = await axios.get(
      `/tables/api/${props.viewname}/search-rows/${props.column.name}`,
      {
        params: { query },
      },
    )
    const data = SearchRowsResponseSchema.parse(response.data)
    const results = data.rows.map((row) => ({
      id: row.id,
      text: row.title,
    }))
    options.value = results
    return results
  } catch (e: unknown) {
    showErrorToast(e, "Search failed")
    options.value = []
    return []
  } finally {
    isLoading.value = false
  }
}

const loadFilterValues = async (
  ids: string[],
): Promise<MultiselectOption[]> => {
  if (ids.length === 0) {
    return []
  }

  try {
    const results = await Promise.all(
      ids.map((id) => searchRelatedRows(id.toString())),
    )
    return results
      .flat()
      .filter(
        (row, index, self) => index === self.findIndex((r) => r.id === row.id),
      )
  } catch (e: unknown) {
    showErrorToast(e, "Failed to load filter values")
    return []
  }
}

watch(
  () => props.humanRowReferences,
  (newHumanRefs) => {
    const currentFilter = props.currentFilter
    if (currentFilter?.d === "fk") {
      const filter = currentFilter as ForeignKeyChoiceFilter
      const humanRefs = newHumanRefs[props.column.name]

      if (humanRefs) {
        const selectedOpts = filter.options
          .map((id) => ({
            id: id,
            text: humanRefs[id] || `ID: ${id}`,
          }))
          .filter(
            (opt, index, self) =>
              index === self.findIndex((o) => o.id === opt.id),
          )

        selectedOptions.value = selectedOpts
        if (options.value.length === 0) {
          options.value = selectedOpts
        }
      }
    }
  },
  { deep: true, immediate: true },
)

watch(
  () => props.currentFilter,
  async (newFilter) => {
    if (!newFilter) {
      selectedOptions.value = []
      options.value = []
      return
    }

    if (newFilter.d === "fk") {
      const filter = newFilter as ForeignKeyChoiceFilter
      const humanRefs = props.humanRowReferences[props.column.name]

      if (humanRefs) {
        const selectedOpts = filter.options
          .map((id) => ({
            id: id,
            text: humanRefs[id] || `ID: ${id}`,
          }))
          .filter(
            (opt, index, self) =>
              index === self.findIndex((o) => o.id === opt.id),
          )

        selectedOptions.value = selectedOpts
        if (options.value.length === 0) {
          options.value = selectedOpts
        }
      } else {
        selectedOptions.value = await loadFilterValues(filter.options)
      }
    }
  },
  { immediate: true },
)

const hasFilter = computed(() => !!props.currentFilter)
const isChoiceFilter = computed(() => props.currentFilter?.d === "fk")
const choiceFilter = computed(
  () => props.currentFilter as ForeignKeyChoiceFilter | undefined,
)
const nullFilter = computed(() =>
  props.currentFilter?.d === "fknull" ? props.currentFilter : undefined,
)

const isAnyActive = computed(
  () => isChoiceFilter.value && choiceFilter.value?.mode === "any",
)
const isNoneActive = computed(
  () => isChoiceFilter.value && choiceFilter.value?.mode === "none",
)

const displayMode = computed(() => {
  if (!isChoiceFilter.value || !choiceFilter.value) return ""
  return choiceFilter.value.mode === "any" ? "any of" : "none of"
})

const displayOptions = computed(() => {
  if (!isChoiceFilter.value) return ""
  const labels = selectedOptions.value.map((opt) => opt.text)
  return labels.join(", ")
})

const submitChoices = (mode: "any" | "none", close: () => void) => {
  const values = [...new Set(selectedOptions.value.map((o) => o.id))]
  if (values.length === 0) {
    props.wrapper.navigateUnsetFilter(props.column.name)
  } else {
    props.wrapper.navigateForeignKeyChoices(props.column.name, mode, values)
  }
  close()
}

const navigateNull = (value: boolean, close: () => void) => {
  props.wrapper.navigateForeignKeyNull(props.column.name, value)
  close()
}

const unset = () => {
  props.wrapper.navigateUnsetFilter(props.column.name)
}
</script>

<template>
  <FilterWrapper
    :columnName="column.name"
    :hasFilter="hasFilter"
    :onUnset="unset"
  >
    <template #collapsed>
      > {{ column.name
      }}<template v-if="isChoiceFilter && choiceFilter">
        <span class="mode_collapsed">{{ displayMode }}</span>
        <span class="options_collapsed">{{ displayOptions }}</span> </template
      ><template v-else-if="nullFilter">
        is
        <span class="null_collapsed">{{
          nullFilter.value ? "null" : "not null"
        }}</span>
      </template>
    </template>

    <template #expanded="{ close }">
      <FilterBox :active="isChoiceFilter">
        <Multiselect
          v-model="selectedOptions"
          :options="options"
          :multiple="true"
          :taggable="false"
          :close-on-select="false"
          :clear-on-select="false"
          :preserve-search="true"
          :internal-search="false"
          :hide-selected="true"
          :allow-empty="true"
          :placeholder="`Search ${props.column.name}...`"
          :loading="isLoading"
          :searchable="true"
          :track-by="'id'"
          :label="'text'"
          :custom-label="(option) => option.text"
          @search-change="searchRelatedRows"
        />

        <button
          @click="submitChoices('any', close)"
          class="filter-button btn-any"
          :class="{ active: isAnyActive }"
        >
          Any of
        </button>
        <button
          @click="submitChoices('none', close)"
          class="filter-button btn-none"
          :class="{ active: isNoneActive }"
        >
          None of
        </button>
      </FilterBox>

      <EmptyFilter
        v-if="!column.required"
        :filter="nullFilter"
        @empty="navigateNull(true, close)"
        @notEmpty="navigateNull(false, close)"
      />
    </template>
  </FilterWrapper>
</template>
