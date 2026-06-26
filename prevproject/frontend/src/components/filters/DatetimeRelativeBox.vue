<script setup lang="ts">
/* eslint-disable no-unused-vars */
import { ref, watch } from "vue"
import FilterBox from "./FilterBox.vue"

interface Props {
  active: boolean
  currentFilter:
    | {
        direction: "past" | "next"
        unit: "hours" | "days" | "months" | "years"
        quantity: number
      }
    | undefined
  onApply: (
    direction: "past" | "next",
    unit: "hours" | "days" | "months" | "years",
    quantity: number,
  ) => void
}
const props = defineProps<Props>()

const direction = ref<"past" | "next">("past")
const unit = ref<"hours" | "days" | "months" | "years">("days")
const quantity = ref(1)

watch(
  () => props.currentFilter,
  (f) => {
    if (!f) {
      direction.value = "past"
      unit.value = "days"
      quantity.value = 1
      return
    }
    direction.value = f.direction
    unit.value = f.unit
    quantity.value = f.quantity
  },
  { immediate: true },
)

const apply = () => {
  props.onApply(direction.value, unit.value, quantity.value)
}
</script>

<template>
  <FilterBox :active="active">
    <select
      v-model="direction"
      class="form-select form-select-sm d-inline-block w-auto"
    >
      <option value="past">Past</option>
      <option value="next">Next</option>
    </select>
    <input
      v-model.number="quantity"
      type="number"
      min="1"
      class="form-control form-control-sm d-inline-block w-auto"
      style="width: 4rem"
    />
    <select
      v-model="unit"
      class="form-select form-select-sm d-inline-block w-auto"
    >
      <option value="hours">hours</option>
      <option value="days">days</option>
      <option value="months">months</option>
      <option value="years">years</option>
    </select>
    <button
      @click="apply"
      class="filter-button btn-relative"
      :class="{ active }"
    >
      Apply
    </button>
  </FilterBox>
</template>
