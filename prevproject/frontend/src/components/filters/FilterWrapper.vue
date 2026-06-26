<script setup lang="ts">
import { ref } from "vue"
import { useFilterHelpers } from "./useFilterHelpers"

interface Props {
  columnName: string
  hasFilter: boolean
  onUnset: () => void
}

const props = defineProps<Props>()

const { wrapperId, wrapperClass, unsetButtonClass } = useFilterHelpers(
  props.columnName,
)

const isOpen = ref(false)

const open = () => {
  isOpen.value = true
}

const close = () => {
  isOpen.value = false
}
</script>

<template>
  <!--
    Collapsed state: rendered when the filter is not open.
    #collapsed slot – display a summary of the active filter (or just the column name).
    Clicking the text button opens the filter; the X button clears it.

    Expanded state: rendered only when the filter is open (v-else ensures the
    collapsed branch is destroyed, so its contents are never eagerly evaluated).
    #expanded slot – receives a `close` function via the scoped slot prop.
    Consumers MUST use it as #expanded="{ close }" and call close() after
    submitting their filter value to collapse back to the summary view.

    Usage:
      <FilterWrapper :columnName="col" :hasFilter="has" :onUnset="unset">
        <template #collapsed>summary text here</template>
        <template #expanded="{ close }">
          ...filter controls...
          <button @click="submit(close)">Apply</button>
        </template>
      </FilterWrapper>
  -->
  <span
    v-if="!isOpen"
    :id="wrapperId"
    class="filter-collapsed filter-widget"
    :class="[wrapperClass, hasFilter ? 'filter-active' : 'filter-inactive']"
  >
    <template v-if="hasFilter">
      <button class="filter-pill" @click="open">
        <slot name="collapsed"></slot>
        <span
          :class="['pill-close-btn', unsetButtonClass]"
          @click.stop="onUnset"
        >
          &times;
        </span>
      </button>
    </template>
    <template v-else>
      <button class="text-left" @click="open">
        <slot name="collapsed"></slot>
      </button>
    </template>
  </span>

  <div
    v-else
    :id="wrapperId"
    class="filter-expanded filter-widget"
    :class="wrapperClass"
  >
    <div class="filter-header">
      <span>{{ columnName }}</span>
      <button :class="['unset-btn', unsetButtonClass]" @click="onUnset">
        X
      </button>
    </div>
    <div class="filter-boxes">
      <slot name="expanded" :close="close"></slot>
    </div>
  </div>
</template>
