<script setup lang="ts">
import { ref, computed, watch } from "vue"
import FilterWrapper from "./FilterWrapper.vue"
import FilterBox from "./FilterBox.vue"
import EmptyFilter from "./EmptyFilter.vue"
import Multiselect from "vue-multiselect"
import type {
  IntegerField,
  IntegerChoiceFilter,
  IntegerNullFilter,
  ListPageSchemaWrapper,
} from "../../schemas"

interface MultiselectOption {
  label: string
  value: number
}

interface Props {
  column: IntegerField
  currentFilter: IntegerChoiceFilter | IntegerNullFilter | undefined
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
    ? props.column.choices.map((c) => ({
        label: c.label,
        value: parseInt(c.value),
      }))
    : [],
)

watch(
  () => props.currentFilter,
  (f) => {
    if (!f || f.d !== "ich") {
      selectedOptions.value = []
      return
    }
    selectedOptions.value = f.options.map((opt) => {
      const choice = props.column.choices?.find(
        (c) => parseInt(c.value) === opt,
      )
      return choice
        ? { label: choice.label, value: opt }
        : { label: opt.toString(), value: opt }
    })
  },
  { immediate: true },
)

const hasFilter = computed(() => !!props.currentFilter)
const isChoiceFilter = computed(() => props.currentFilter?.d === "ich")
const choiceFilter = computed(
  () => props.currentFilter as IntegerChoiceFilter | undefined,
)
const nullFilter = computed(() =>
  props.currentFilter?.d === "null" ? props.currentFilter : undefined,
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
    const choice = props.column.choices?.find((c) => parseInt(c.value) === opt)
    return choice ? choice.label : opt.toString()
  })
  return labels.join(", ")
})

const submitChoices = (mode: "any" | "none", close: () => void) => {
  const values = selectedOptions.value.map((o: MultiselectOption) => o.value)
  props.wrapper.navigateIntegerChoices(props.column.name, mode, values)
  close()
}

const navigateNull = (value: boolean, close: () => void) => {
  props.wrapper.navigateIntegerNullValue(props.column.name, value)
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
        v-if="!column.required"
        :filter="nullFilter"
        @empty="navigateNull(true, close)"
        @notEmpty="navigateNull(false, close)"
      />
    </template>
  </FilterWrapper>
</template>
