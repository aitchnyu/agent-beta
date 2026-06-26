<script setup lang="ts">
/* eslint-disable no-unused-vars */
import { ref, watch } from "vue"
import FilterBox from "./FilterBox.vue"

interface Props {
  active: boolean
  currentFilter:
    | { op: string; number_1: string; number_2: string | undefined }
    | undefined
  onApply: (
    operator: "eq" | "gt" | "lt" | "gte" | "lte" | "ne" | "inc" | "ex",
    number1: string,
    number2: string,
  ) => void
}
const props = defineProps<Props>()

const operator = ref<"eq" | "gt" | "lt" | "gte" | "lte" | "ne" | "inc" | "ex">(
  "gt",
)
const number1 = ref("0")
const number2 = ref("0")

watch(
  () => props.currentFilter,
  (f) => {
    if (!f) {
      operator.value = "gt"
      number1.value = "0"
      number2.value = "0"
      return
    }
    operator.value = f.op as
      | "eq"
      | "gt"
      | "lt"
      | "gte"
      | "lte"
      | "ne"
      | "inc"
      | "ex"
    number1.value = f.number_1
    number2.value = f.number_2 ?? "0"
  },
  { immediate: true },
)

const apply = () => {
  props.onApply(operator.value, number1.value, number2.value)
}
</script>

<template>
  <FilterBox :active="active">
    <select
      v-model="operator"
      class="form-select form-select-sm d-inline-block w-auto"
    >
      <option value="eq">equals</option>
      <option value="gt">greater than</option>
      <option value="lt">less than</option>
      <option value="gte">greater or equal</option>
      <option value="lte">less or equal</option>
      <option value="ne">not equals</option>
      <option value="inc">include range</option>
      <option value="ex">exclude range</option>
    </select>
    <input
      v-model="number1"
      type="text"
      inputmode="decimal"
      class="form-control form-control-sm d-inline-block w-auto"
    />
    <input
      v-if="operator === 'inc' || operator === 'ex'"
      v-model="number2"
      type="text"
      inputmode="decimal"
      class="form-control form-control-sm d-inline-block w-auto"
    />
    <button
      @click="apply"
      class="filter-button btn-compare"
      :class="{ active }"
    >
      Apply
    </button>
  </FilterBox>
</template>
