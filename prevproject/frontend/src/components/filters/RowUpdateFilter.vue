<script setup lang="ts">
import { ref, computed, watch } from "vue"
import axios from "axios"
import FilterWrapper from "./FilterWrapper.vue"
import FilterBox from "./FilterBox.vue"
import Multiselect from "vue-multiselect"
import type { RowUpdateFilter, ListPageSchemaWrapper } from "../../schemas"
import { showErrorToast } from "../../utils/sweetalert"

interface UserOption {
  id: string
  title: string
}

interface Props {
  currentFilter: RowUpdateFilter | undefined
  wrapper: ListPageSchemaWrapper
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Inertia props are untyped
  humanRowReferences: Record<string, any>
  userViewname: string | null | undefined
}

const props = defineProps<Props>()

const selectedUsers = ref<UserOption[]>([])
const userOptions = ref<UserOption[]>([])
const isUserLoading = ref(false)
const selectedActions = ref<("created_row" | "updated_row" | "commented")[]>([])
const dateFrom = ref<string>("")
const dateTo = ref<string>("")

const ACTION_OPTIONS: ("created_row" | "updated_row" | "commented")[] = [
  "created_row",
  "updated_row",
  "commented",
]

const ACTION_LABELS: Record<string, string> = {
  created_row: "Created",
  updated_row: "Updated",
  commented: "Commented",
}

const searchUsers = async (query: string): Promise<void> => {
  if (query.length < 2) {
    userOptions.value = []
    return
  }

  try {
    isUserLoading.value = true
    const response = await axios.get("/tables/api/_search-users", {
      params: { q: query },
    })
    const users = response.data.rows.map(
      (u: { id: string; title: string }) => ({
        id: u.id,
        title: u.title,
      }),
    )
    userOptions.value = users
  } catch (e: unknown) {
    showErrorToast(e, "User search failed")
    userOptions.value = []
  } finally {
    isUserLoading.value = false
  }
}

watch(
  () => props.currentFilter,
  (newFilter) => {
    if (!newFilter) {
      selectedUsers.value = []
      selectedActions.value = []
      dateFrom.value = ""
      dateTo.value = ""
      return
    }

    selectedActions.value = newFilter.actions || []

    if (newFilter.date_from) {
      dateFrom.value = newFilter.date_from.slice(0, 16)
    } else {
      dateFrom.value = ""
    }

    if (newFilter.date_to) {
      dateTo.value = newFilter.date_to.slice(0, 16)
    } else {
      dateTo.value = ""
    }

    if (newFilter.user_ids && newFilter.user_ids.length > 0) {
      const userRefs =
        (props.userViewname && props.humanRowReferences[props.userViewname]) ||
        {}
      const users = newFilter.user_ids.map((id) => ({
        id,
        title: userRefs[id] || `User ${id}`,
      }))
      selectedUsers.value = users
      userOptions.value = users
    } else {
      selectedUsers.value = []
    }
  },
  { immediate: true },
)

const hasFilter = computed(() => !!props.currentFilter)

const displayUsers = computed(() => {
  return selectedUsers.value.map((u) => u.title).join(", ")
})

const displayActions = computed(() => {
  return selectedActions.value.map((a) => ACTION_LABELS[a]).join(", ")
})

const displayDateRange = computed(() => {
  const parts: string[] = []
  if (dateFrom.value) {
    parts.push(`from ${new Date(dateFrom.value).toLocaleDateString()}`)
  }
  if (dateTo.value) {
    parts.push(`to ${new Date(dateTo.value).toLocaleDateString()}`)
  }
  return parts.join(" ")
})

const collapsedText = computed(() => {
  if (!props.currentFilter) {
    return "> Row Update"
  }

  const parts: string[] = ["> Row Update"]

  if (selectedUsers.value.length > 0) {
    parts.push(displayUsers.value)
  }

  if (selectedActions.value.length > 0) {
    parts.push(`[${displayActions.value}]`)
  }

  if (dateFrom.value || dateTo.value) {
    parts.push(displayDateRange.value)
  }

  return parts.join(" ")
})

const submitFilter = (close: () => void) => {
  const userIds =
    selectedUsers.value.length > 0 ? selectedUsers.value.map((u) => u.id) : null

  const actions =
    selectedActions.value.length > 0 && selectedActions.value.length < 3
      ? [...selectedActions.value]
      : null

  const dateFromVal = dateFrom.value || null
  const dateToVal = dateTo.value || null

  props.wrapper.navigateRowUpdateFilter(
    userIds,
    actions,
    dateFromVal,
    dateToVal,
  )
  close()
}

const unset = () => {
  props.wrapper.navigateUnsetRowUpdateFilter()
}
</script>

<template>
  <FilterWrapper
    columnName="Row Update"
    :hasFilter="hasFilter"
    :onUnset="unset"
  >
    <template #collapsed>{{ collapsedText }}</template>

    <template #expanded="{ close }">
      <FilterBox :active="hasFilter">
        <div class="row-update-filter-section">
          <label class="filter-label">Users:</label>
          <Multiselect
            v-model="selectedUsers"
            :options="userOptions"
            :multiple="true"
            :taggable="false"
            :close-on-select="false"
            :clear-on-select="false"
            :preserve-search="true"
            :internal-search="false"
            :hide-selected="true"
            :allow-empty="true"
            placeholder="Search users..."
            :loading="isUserLoading"
            :searchable="true"
            :track-by="'id'"
            :label="'title'"
            :custom-label="(option: UserOption) => option.title"
            @search-change="searchUsers"
          />
        </div>

        <div class="row-update-filter-section">
          <label class="filter-label">Actions:</label>
          <div class="action-checkboxes">
            <label
              v-for="action in ACTION_OPTIONS"
              :key="action"
              class="action-checkbox"
            >
              <input
                type="checkbox"
                :value="action"
                v-model="selectedActions"
              />
              {{ ACTION_LABELS[action] }}
            </label>
          </div>
        </div>

        <div class="row-update-filter-section">
          <label class="filter-label">Date Range:</label>
          <div class="date-range-inputs">
            <input
              type="datetime-local"
              v-model="dateFrom"
              class="date-input"
              placeholder="From"
            />
            <span class="date-separator">to</span>
            <input
              type="datetime-local"
              v-model="dateTo"
              class="date-input"
              placeholder="To"
            />
          </div>
        </div>

        <div class="row-update-filter-buttons">
          <button @click="submitFilter(close)" class="filter-button btn-apply">
            Apply Filter
          </button>
        </div>
      </FilterBox>
    </template>
  </FilterWrapper>
</template>
