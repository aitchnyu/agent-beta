<script setup lang="ts">
import { computed } from "vue"
import FilterWrapper from "./FilterWrapper.vue"
import DecimalComparisonBox from "./DecimalComparisonBox.vue"
import EmptyFilter from "./EmptyFilter.vue"
import type {
  DecimalField,
  DecimalComparisonFilter,
  DecimalNullFilter,
  ListPageSchemaWrapper,
} from "../../schemas"

interface Props {
  column: DecimalField
  currentFilter: DecimalComparisonFilter | DecimalNullFilter | undefined
  wrapper: ListPageSchemaWrapper
}
const props = defineProps<Props>()

const hasFilter = computed(() => !!props.currentFilter)
const isComparisonFilter = computed(() => props.currentFilter?.d === "dcomp")
const comparisonFilter = computed(() =>
  props.currentFilter?.d === "dcomp"
    ? (props.currentFilter as {
        number_1: string
        number_2: string | undefined
        op: string
      })
    : undefined,
)
const isRangeOperator = computed(
  () =>
    isComparisonFilter.value &&
    comparisonFilter.value &&
    (comparisonFilter.value.op === "inc" || comparisonFilter.value.op === "ex"),
)
const nullFilter = computed(() =>
  props.currentFilter?.d === "dnull" ? props.currentFilter : undefined,
)

const displayOperator = computed(() => {
  if (!isComparisonFilter.value || !comparisonFilter.value) return ""
  const op = comparisonFilter.value.op
  if (op === "inc") return "inc"
  if (op === "ex") return "exclude"
  return op
})

const submitCompare = (
  operator: "eq" | "gt" | "lt" | "gte" | "lte" | "ne" | "inc" | "ex",
  number1: string,
  number2: string,
  close: () => void,
) => {
  props.wrapper.navigateDecimalCompare(
    props.column.name,
    operator,
    number1,
    number2,
  )
  close()
}

const navigateNull = (value: boolean, close: () => void) => {
  props.wrapper.navigateDecimalNull(props.column.name, value)
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
      >
      {{ column.name }}
      <template v-if="isComparisonFilter && comparisonFilter">
        <span class="operator_collapsed">{{ displayOperator }}</span>
        <span class="number_1_collapsed">{{ comparisonFilter.number_1 }}</span>
        <template v-if="isRangeOperator && comparisonFilter.number_2">
          -
          <span class="number_2_collapsed">{{
            comparisonFilter.number_2
          }}</span>
        </template> </template
      ><template v-else-if="nullFilter">
        is
        <span class="null_collapsed">{{
          nullFilter.value ? "null" : "not null"
        }}</span>
      </template>
    </template>

    <template #expanded="{ close }">
      <DecimalComparisonBox
        :active="isComparisonFilter"
        :currentFilter="comparisonFilter"
        :onApply="(op, n1, n2) => submitCompare(op, n1, n2, close)"
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
