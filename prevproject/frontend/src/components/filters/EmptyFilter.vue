<script setup lang="ts">
import { computed } from "vue"
import FilterBox from "./FilterBox.vue"

interface Props {
  filter: { value: boolean } | undefined
  labelEmpty?: string
  labelNotEmpty?: string
  onEmpty: () => void
  onNotEmpty: () => void
  classEmpty?: string
  classNotEmpty?: string
}
const props = defineProps<Props>()

const isEmptyActive = computed(() => props.filter?.value === true)
const isNotEmptyActive = computed(() => props.filter?.value === false)
const defaultClassEmpty = computed(() => props.classEmpty ?? "btn-is-null")
const defaultClassNotEmpty = computed(
  () => props.classNotEmpty ?? "btn-not-null",
)
</script>

<template>
  <FilterBox :active="isEmptyActive || isNotEmptyActive">
    <button
      :class="['filter-button', defaultClassEmpty, { active: isEmptyActive }]"
      @click="onEmpty"
    >
      {{ labelEmpty ?? "Empty" }}
    </button>
    <button
      :class="[
        'filter-button',
        defaultClassNotEmpty,
        { active: isNotEmptyActive },
      ]"
      @click="onNotEmpty"
    >
      {{ labelNotEmpty ?? "Not empty" }}
    </button>
  </FilterBox>
</template>
