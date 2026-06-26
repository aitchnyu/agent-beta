import { computed } from "vue"

export function useFilterHelpers(columnName: string) {
  const wrapperId = computed(() => `filter-widget-${columnName}`)
  const wrapperClass = computed(() => `filter-widget-${columnName}`)
  const unsetButtonClass = computed(() => `unset-filter-${columnName}`)
  return { wrapperId, wrapperClass, unsetButtonClass }
}
