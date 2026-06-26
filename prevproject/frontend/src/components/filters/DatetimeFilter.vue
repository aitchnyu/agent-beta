<script setup lang="ts">
import { computed } from "vue"
import FilterWrapper from "./FilterWrapper.vue"
import DatetimeComparisonBox from "./DatetimeComparisonBox.vue"
import DatetimeRelativeBox from "./DatetimeRelativeBox.vue"
import EmptyFilter from "./EmptyFilter.vue"
import type {
  DateTimeField,
  DatetimeComparisonFilter,
  DatetimeNullFilter,
  DatetimeRelativeFilter,
  ListPageSchemaWrapper,
} from "../../schemas"

interface Props {
  column: DateTimeField
  currentFilter:
    | DatetimeComparisonFilter
    | DatetimeNullFilter
    | DatetimeRelativeFilter
    | undefined
  wrapper: ListPageSchemaWrapper
}
const props = defineProps<Props>()

const hasFilter = computed(() => !!props.currentFilter)
const isComparisonFilter = computed(() => props.currentFilter?.d === "dtcomp")
const isRelativeFilter = computed(() => props.currentFilter?.d === "dtrel")
const isNullFilter = computed(() => props.currentFilter?.d === "dtnull")
const comparisonFilter = computed(() => {
  if (props.currentFilter?.d === "dtcomp") {
    const f = props.currentFilter
    return {
      op: f.op,
      datetime_1: f.datetime_1,
      datetime_2: f.datetime_2,
    }
  }
  return undefined
})
const relativeFilter = computed(() => {
  if (props.currentFilter?.d === "dtrel") {
    const f = props.currentFilter
    return { direction: f.direction, unit: f.unit, quantity: f.quantity }
  }
  return undefined
})
const nullFilter = computed(() => {
  if (props.currentFilter?.d === "dtnull") {
    const f = props.currentFilter
    return { value: f.value }
  }
  return undefined
})

const isRangeOperator = computed(
  () =>
    isComparisonFilter.value &&
    comparisonFilter.value &&
    (comparisonFilter.value.op === "inc" || comparisonFilter.value.op === "ex"),
)

const submitCompare = (
  operator: "eq" | "gt" | "lt" | "gte" | "lte" | "ne" | "inc" | "ex",
  datetime1: string,
  datetime2: string,
  close: () => void,
) => {
  props.wrapper.navigateDatetimeCompare(
    props.column.name,
    operator,
    datetime1,
    datetime2,
  )
  close()
}

const submitRelative = (
  direction: "past" | "next",
  unit: "hours" | "days" | "months" | "years",
  quantity: number,
  close: () => void,
) => {
  props.wrapper.navigateDatetimeRelative(
    props.column.name,
    direction,
    unit,
    quantity,
  )
  close()
}

const navigateNull = (value: boolean, close: () => void) => {
  props.wrapper.navigateDatetimeNull(props.column.name, value)
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
      }}<template v-if="isComparisonFilter && comparisonFilter">
        <span class="operator_collapsed">{{ comparisonFilter.op }}</span>
        <span class="datetime_1_collapsed">{{
          new Date(comparisonFilter.datetime_1).toLocaleString()
        }}</span
        ><template v-if="isRangeOperator">
          -
          <span class="datetime_2_collapsed">{{
            new Date(comparisonFilter.datetime_2).toLocaleString()
          }}</span>
        </template> </template
      ><template v-else-if="isRelativeFilter && relativeFilter">
        <span class="direction_collapsed">{{ relativeFilter.direction }}</span>
        <span class="quantity_collapsed">{{ relativeFilter.quantity }}</span>
        <span class="unit_collapsed">{{ relativeFilter.unit }}</span> </template
      ><template v-else-if="isNullFilter && nullFilter">
        <span class="null_collapsed">{{
          nullFilter.value ? "is null" : "not null"
        }}</span>
      </template>
    </template>

    <template #expanded="{ close }">
      <DatetimeComparisonBox
        :active="isComparisonFilter"
        :currentFilter="comparisonFilter"
        :onApply="(op, dt1, dt2) => submitCompare(op, dt1, dt2, close)"
      />
      <DatetimeRelativeBox
        :active="isRelativeFilter"
        :currentFilter="relativeFilter"
        :onApply="(dir, unit, qty) => submitRelative(dir, unit, qty, close)"
      />
      <EmptyFilter
        v-if="!column.required"
        :filter="nullFilter"
        @empty="navigateNull(true, close)"
        @notEmpty="navigateNull(false, close)"
      />
    </template>
  </FilterWrapper>
</template>
