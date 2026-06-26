<script setup lang="ts">
import { ref, computed, watch } from "vue"
import FilterWrapper from "./FilterWrapper.vue"
import FilterBox from "./FilterBox.vue"
import EmptyFilter from "./EmptyFilter.vue"
import Multiselect from "vue-multiselect"
import type {
  CharField,
  CharChoiceFilter,
  CharBlankFilter,
  ListPageSchemaWrapper,
} from "../../schemas"

interface MultiselectOption {
  label: string
  value: string
}

interface Props {
  column: CharField
  currentFilter: CharChoiceFilter | CharBlankFilter | undefined
  wrapper: ListPageSchemaWrapper
}

const props = defineProps<Props>()

const selectedOptions = ref<MultiselectOption[]>([])

// Computed so the array and its objects are referentially stable across
// renders (only recomputes when column.choices changes).  vue-multiselect
// with track-by="value" needs stable option objects so that internal
// identity checks (isSelected / removeElement) work correctly.  An inline
// :options="choices.map(...)" would create new objects every render,
// breaking deselection and duplicate detection.
const multiselectOptions = computed<MultiselectOption[]>(() =>
  props.column.choices
    ? props.column.choices.map((c) => ({ label: c.label, value: c.value }))
    : [],
)

watch(
  () => props.currentFilter,
  (f) => {
    if (!f || f.d !== "cc") {
      selectedOptions.value = []
      return
    }
    selectedOptions.value = f.options.map((opt) => {
      const choice = props.column.choices?.find((c) => c.value === opt)
      return choice
        ? { label: choice.label, value: opt }
        : { label: opt, value: opt }
    })
  },
  { immediate: true },
)

const hasFilter = computed(() => !!props.currentFilter)
const isChoiceFilter = computed(() => props.currentFilter?.d === "cc")
const choiceFilter = computed(
  () => props.currentFilter as CharChoiceFilter | undefined,
)
const blankFilter = computed(() =>
  props.currentFilter?.d === "cb" ? props.currentFilter : undefined,
)

const isAnyActive = computed(
  () => isChoiceFilter.value && choiceFilter.value?.mode === "any",
)
const isNoneActive = computed(
  () => isChoiceFilter.value && choiceFilter.value?.mode === "none",
)

const displayMode = computed(() => {
  if (!isChoiceFilter.value || !choiceFilter.value) return ""
  return choiceFilter.value.mode === "any" ? "all of" : "none of"
})

const displayOptions = computed(() => {
  if (!isChoiceFilter.value || !choiceFilter.value) return ""
  const labels = choiceFilter.value.options.map((opt) => {
    const choice = props.column.choices?.find((c) => c.value === opt)
    return choice ? choice.label : opt
  })
  return labels.join(", ")
})

const submitChoices = (mode: "any" | "none", close: () => void) => {
  const values = selectedOptions.value.map((o) => o.value)
  props.wrapper.navigateCharChoices(props.column.name, mode, values)
  close()
}

const navigateBlank = (value: boolean, close: () => void) => {
  props.wrapper.navigateCharBlank(props.column.name, value)
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
      > {{ column.name }}
      <template v-if="isChoiceFilter && choiceFilter">
        <span class="mode_collapsed">{{ displayMode }}</span>
        <span class="options_collapsed">
          {{ displayOptions }}
        </span>
      </template>
      <template v-else-if="blankFilter">
        is
        <span class="blank_collapsed">
          {{ blankFilter.value ? "blank" : "not blank" }}
        </span>
      </template>
    </template>

    <template #expanded="{ close }">
      <FilterBox :active="isChoiceFilter">
        <multiselect
          v-model="selectedOptions"
          :options="multiselectOptions"
          label="label"
          track-by="value"
          placeholder="Select options"
          multiple
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
        :filter="blankFilter"
        @empty="navigateBlank(true, close)"
        @notEmpty="navigateBlank(false, close)"
      />
    </template>
  </FilterWrapper>
</template>
