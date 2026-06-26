<script setup lang="ts">
import { ref, computed } from "vue"
import FilterWrapper from "../filters/FilterWrapper.vue"
import type { ListPageSchemaWrapper } from "../../ListPageSchemaWrapper"

interface Props {
  wrapper: ListPageSchemaWrapper
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- custom key value is untyped
  currentValue: any
}

const props = defineProps<Props>()

type DiffValue = "any" | number | undefined
const currentDiff = ref<DiffValue>(
  props.currentValue === undefined
    ? undefined
    : (props.currentValue as DiffValue),
)
const hasFilter = computed(() => currentDiff.value != null)
const diffInput = ref<string>(
  typeof currentDiff.value === "number" ? String(currentDiff.value) : "",
)

const collapsedLabel = computed(() => {
  if (currentDiff.value === undefined) return ""
  if (currentDiff.value === "any") return "any positive"
  return `>= ${currentDiff.value}`
})

function submitAny(close: () => void) {
  props.wrapper.navigateCustom("diff", "any")
  close()
}

function submitInt(close: () => void) {
  const num = parseInt(diffInput.value, 10)
  if (!isNaN(num) && num > 0) {
    props.wrapper.navigateCustom("diff", num)
    close()
  }
}

function unset() {
  diffInput.value = ""
  props.wrapper.navigateCustom("diff", undefined)
}
</script>

<template>
  <FilterWrapper columnName="diff" :hasFilter="hasFilter" :onUnset="unset">
    <template #collapsed>
      > diff<template v-if="hasFilter">
        <span class="diff_collapsed">{{ collapsedLabel }}</span>
      </template>
    </template>

    <template #expanded="{ close }">
      <button
        class="filter-button btn-diff-any"
        :class="{ active: currentDiff === 'any' }"
        @click="submitAny(close)"
      >
        Any positive
      </button>
      <input
        v-model="diffInput"
        type="number"
        min="1"
        class="form-control form-control-sm d-inline-block w-auto diff-input"
        placeholder="Min diff"
        @keyup.enter="submitInt(close)"
      />
      <button class="filter-button btn-diff-int" @click="submitInt(close)">
        Apply
      </button>
    </template>
  </FilterWrapper>
</template>
