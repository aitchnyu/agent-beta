<script setup lang="ts">
import { ref, computed, watch } from "vue"
import FilterWrapper from "./FilterWrapper.vue"
import FilterBox from "./FilterBox.vue"
import EmptyFilter from "./EmptyFilter.vue"
import type {
  CharField,
  TextField,
  CharTextFilter,
  CharBlankFilter,
  ListPageSchemaWrapper,
} from "../../schemas"

interface Props {
  column: CharField | TextField
  currentFilter: CharTextFilter | CharBlankFilter | undefined
  wrapper: ListPageSchemaWrapper
}
const props = defineProps<Props>()

const textInput = ref("")

watch(
  () => props.currentFilter,
  (f) => {
    if (!f || f.d !== "ct") {
      textInput.value = ""
      return
    }
    textInput.value = f.text
  },
  { immediate: true },
)

const hasFilter = computed(() => !!props.currentFilter)
const isTextFilter = computed(() => props.currentFilter?.d === "ct")
const textFilter = computed(
  () => props.currentFilter as CharTextFilter | undefined,
)
const blankFilter = computed(() =>
  props.currentFilter?.d === "cb" ? props.currentFilter : undefined,
)

const submitText = (close: () => void) => {
  if (textInput.value.trim()) {
    props.wrapper.navigateCharText(props.column.name, textInput.value)
    close()
  }
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
      > {{ column.name
      }}<template v-if="isTextFilter && textFilter">
        contains
        <span class="text_collapsed">{{ textFilter.text }}</span> </template
      ><template v-else-if="blankFilter">
        is
        <span class="blank_collapsed">{{
          blankFilter.value ? "blank" : "not blank"
        }}</span>
      </template>
    </template>

    <template #expanded="{ close }">
      <FilterBox :active="isTextFilter">
        <input
          v-model="textInput"
          type="text"
          class="form-control form-control-sm d-inline-block w-auto"
          placeholder="Contains text"
          @keyup.enter="submitText(close)"
        />
        <button
          @click="submitText(close)"
          class="filter-button btn-contains"
          :class="{ active: isTextFilter }"
        >
          Contains
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
