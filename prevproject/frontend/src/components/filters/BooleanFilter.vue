<script setup lang="ts">
import { computed } from "vue"
import FilterWrapper from "./FilterWrapper.vue"
import FilterBox from "./FilterBox.vue"
import type {
  BooleanField,
  BooleanValueFilter,
  ListPageSchemaWrapper,
} from "../../schemas"

interface Props {
  column: BooleanField
  currentFilter: BooleanValueFilter | undefined
  wrapper: ListPageSchemaWrapper
}
const props = defineProps<Props>()

const hasFilter = computed(() => !!props.currentFilter)
const isYesActive = computed(() => props.currentFilter?.value === true)
const isNoActive = computed(() => props.currentFilter?.value === false)

const displayValue = computed(() => {
  if (!props.currentFilter) return ""
  return props.currentFilter.value ? "Yes" : "No"
})

const collapsedText = computed(() => {
  if (!props.currentFilter) {
    return `> ${props.column.name}`
  }
  return `> ${props.column.name} ${displayValue.value}`
})

const setYes = (close: () => void) => {
  props.wrapper.navigateBooleanValue(props.column.name, true)
  close()
}

const setNo = (close: () => void) => {
  props.wrapper.navigateBooleanValue(props.column.name, false)
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
    <template #collapsed>{{ collapsedText }}</template>

    <template #expanded="{ close }">
      <FilterBox :active="hasFilter">
        <button
          @click="setYes(close)"
          class="filter-button btn-yes"
          :class="{ active: isYesActive }"
        >
          Yes
        </button>
        <button
          @click="setNo(close)"
          class="filter-button btn-no"
          :class="{ active: isNoActive }"
        >
          No
        </button>
      </FilterBox>
    </template>
  </FilterWrapper>
</template>
