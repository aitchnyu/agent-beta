<script setup lang="ts">
/* eslint-disable no-unused-vars */
import { ref, watch } from "vue"
import FilterBox from "./FilterBox.vue"

interface Props {
  active: boolean
  currentFilter:
    | { op: string; datetime_1: string; datetime_2: string }
    | undefined
  onApply: (
    operator: "eq" | "gt" | "lt" | "gte" | "lte" | "ne" | "inc" | "ex",
    datetime1: string,
    datetime2: string,
  ) => void
}
const props = defineProps<Props>()

const getMidnightISO = (): string => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}T00:00`
}

const operator = ref<"eq" | "gt" | "lte" | "gte" | "ne" | "inc" | "ex">("gt")
const datetime1 = ref(getMidnightISO())
const datetime2 = ref(getMidnightISO())

watch(
  () => props.currentFilter,
  (f) => {
    if (!f) {
      operator.value = "gt"
      datetime1.value = getMidnightISO()
      datetime2.value = getMidnightISO()
      return
    }
    operator.value = f.op as "eq" | "gt" | "lte" | "gte" | "ne" | "inc" | "ex"
    datetime1.value = f.datetime_1
    datetime2.value = f.datetime_2
  },
  { immediate: true },
)

const submitCompare = () => {
  props.onApply(operator.value, datetime1.value, datetime2.value)
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
      <option value="gte">greater or equal</option>
      <option value="lt">less than</option>
      <option value="lte">less or equal</option>
      <option value="ne">not equals</option>
      <option value="inc">include range</option>
      <option value="ex">exclude range</option>
    </select>
    <input
      v-model="datetime1"
      type="datetime-local"
      class="form-control form-control-sm d-inline-block w-auto"
    />
    <input
      v-if="operator === 'inc' || operator === 'ex'"
      v-model="datetime2"
      type="datetime-local"
      class="form-control form-control-sm d-inline-block w-auto"
    />
    <button
      @click="submitCompare"
      class="filter-button btn-compare"
      :class="{ active }"
    >
      Apply
    </button>
  </FilterBox>
</template>
