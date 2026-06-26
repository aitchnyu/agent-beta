<script setup lang="ts">
import { router } from "@inertiajs/vue3"
import { computed, ref } from "vue"
import { rowDetailsUrl } from "../utils/urls"

interface Row {
  id: string
  title: string
}

const props = defineProps<{
  rows: Row[]
  viewname: string
}>()

const showSearch = ref(false)
const searchQuery = ref("")
const searchInput = ref<HTMLInputElement | null>(null)
const activeIndex = ref(-1)

function toggleSearch() {
  showSearch.value = !showSearch.value
  if (showSearch.value) {
    activeIndex.value = -1
    setTimeout(() => {
      searchInput.value?.focus()
    }, 0)
  } else {
    searchQuery.value = ""
    activeIndex.value = -1
  }
}

const searchResults = computed(() => {
  if (!searchQuery.value) return []
  const q = searchQuery.value.toLowerCase()
  return props.rows.filter(
    (row) =>
      row.title.toLowerCase().includes(q) || row.id.toLowerCase().includes(q),
  )
})

function navigateToRow(rowId: string) {
  router.visit(rowDetailsUrl(props.viewname, rowId))
  showSearch.value = false
  searchQuery.value = ""
  activeIndex.value = -1
}

function handleKeydown(e: KeyboardEvent) {
  if (!searchResults.value.length) return

  if (e.key === "ArrowDown") {
    e.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % searchResults.value.length
  } else if (e.key === "ArrowUp") {
    e.preventDefault()
    activeIndex.value =
      activeIndex.value <= 0
        ? searchResults.value.length - 1
        : activeIndex.value - 1
  } else if (e.key === "Enter" && activeIndex.value >= 0) {
    e.preventDefault()
    navigateToRow(searchResults.value[activeIndex.value]!.id)
  }
}
</script>

<template>
  <th class="col-id" :class="{ 'col-id-expanded': showSearch }">
    <button
      v-if="!showSearch"
      class="search-toggle-btn"
      title="Search rows"
      @click="toggleSearch"
    >
      &#128269;
    </button>
    <template v-else>
      <input
        ref="searchInput"
        v-model="searchQuery"
        class="form-control search-input"
        placeholder="Search rows..."
        @keydown.escape="toggleSearch"
        @keydown="handleKeydown"
      />
      <div v-if="searchResults.length > 0" class="search-results-dropdown">
        <div
          v-for="(result, index) in searchResults"
          :key="result.id"
          class="search-result-item"
          :class="{ 'search-result-active': index === activeIndex }"
          @click="navigateToRow(result.id)"
        >
          {{ result.title }}
        </div>
      </div>
    </template>
  </th>
</template>
