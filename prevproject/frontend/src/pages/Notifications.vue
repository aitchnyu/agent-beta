<script setup lang="ts">
import { z } from "zod"
import { ref, type PropType } from "vue"
import { Link, router } from "@inertiajs/vue3"
import axios from "axios"
import { showErrorToast, showToast, showConfirm } from "../utils/sweetalert"
import { rowDetailsUrl } from "../utils/urls"
import Layout from "../components/Layout.vue"
import RenderRawHtml from "../components/RenderRawHtml.vue"
import ExpandableCell from "../components/ExpandableCell.vue"
import RowColumnValues from "../components/RowColumnValues.vue"
import { RowUpdateResponseSchema } from "../schemas"
import { formatDateTime, getActionLabel } from "../utils/rowUpdate"

type RowUpdateItem = z.infer<typeof RowUpdateResponseSchema>

interface NotificationItem {
  id: string
  viewname: string
  row_public_id: string
  row_update: RowUpdateItem
}

interface NotificationsProps {
  user: { id: string; title: string } | null
  notifications: NotificationItem[]
  viewname_counts: Record<string, number>
  total_count: number
  current_page: number
  total_pages: number
  active_viewname: string | null
}

const props = defineProps({
  props: {
    type: Object as PropType<NotificationsProps>,
    required: true,
  },
})

const p = props.props

const parsedNotifications = p.notifications.map((n) => ({
  ...n,
  row_update: RowUpdateResponseSchema.parse(n.row_update),
}))

const selectedIds = ref<Set<string>>(new Set())
const activeViewname = ref<string | null>(p.active_viewname ?? null)

const visitPage = (page: number, viewname: string | null = null) => {
  const params = new URLSearchParams()
  params.set("page", String(page))
  if (viewname) {
    params.set("viewname", viewname)
  }
  router.visit(`/tables/notifications/page?${params.toString()}`)
}

const filterByViewname = (viewname: string | null) => {
  activeViewname.value = viewname
  visitPage(1, viewname)
}

const goToPage = (page: number) => {
  visitPage(page, activeViewname.value)
}

const toggleSelect = (id: string) => {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
}

const toggleSelectAll = () => {
  if (selectedIds.value.size === parsedNotifications.length) {
    selectedIds.value.clear()
  } else {
    selectedIds.value = new Set(parsedNotifications.map((n) => n.id))
  }
}

const deleteSelected = async () => {
  if (selectedIds.value.size === 0) return
  try {
    await axios.post("/tables/api/notifications/delete", {
      notification_ids: Array.from(selectedIds.value),
    })
    showToast("success", "Notifications deleted")
    router.reload()
  } catch (e: unknown) {
    showErrorToast(e, "Failed to delete notifications")
  }
}

const clearAll = async () => {
  const confirmed = await showConfirm({
    title: "Clear all notifications?",
    confirmButtonText: "Yes, clear all",
  })
  if (!confirmed) return
  try {
    await axios.post("/tables/api/notifications/clear", {
      viewname: activeViewname.value || undefined,
    })
    showToast("success", "Notifications cleared")
    visitPage(1, activeViewname.value)
  } catch (e: unknown) {
    showErrorToast(e, "Failed to clear notifications")
  }
}
</script>

<template>
  <Layout :user="p.user">
    <div class="container">
      <h1>Notifications ({{ p.total_count }})</h1>

      <div class="notifications-layout">
        <div class="notifications-sidebar">
          <button
            class="filter-btn"
            :class="{ active: activeViewname === null }"
            @click="filterByViewname(null)"
          >
            All ({{ p.total_count }})
          </button>
          <button
            v-for="(count, vn) in p.viewname_counts"
            :key="vn"
            class="filter-btn"
            :class="{ active: activeViewname === vn }"
            @click="filterByViewname(vn as string)"
          >
            {{ vn }} ({{ count }})
          </button>
        </div>

        <div class="notifications-main">
          <div v-if="parsedNotifications.length === 0" class="no-notifications">
            No notifications
          </div>

          <template v-else>
            <div class="notifications-actions">
              <label class="select-all-label">
                <input
                  type="checkbox"
                  :checked="
                    selectedIds.size === parsedNotifications.length &&
                    parsedNotifications.length > 0
                  "
                  @change="toggleSelectAll"
                />
                Select all
              </label>
              <button
                v-if="selectedIds.size > 0"
                class="btn btn-sm btn-outline-danger delete-selected-btn"
                @click="deleteSelected"
              >
                Delete selected ({{ selectedIds.size }})
              </button>
              <button
                class="btn btn-sm btn-outline-danger clear-all-btn"
                @click="clearAll"
              >
                Clear all{{ activeViewname ? ` ${activeViewname}` : "" }}
              </button>
            </div>

            <div class="notifications-list">
              <div
                v-for="item in parsedNotifications"
                :key="item.id"
                class="notification-item"
              >
                <input
                  type="checkbox"
                  class="notification-checkbox"
                  :checked="selectedIds.has(item.id)"
                  @change="toggleSelect(item.id)"
                />
                <div class="notification-content">
                  <div class="notification-header">
                    <Link
                      :href="rowDetailsUrl(item.viewname, item.row_public_id)"
                      class="notification-link"
                    >
                      {{ item.viewname }} #{{ item.row_public_id }}
                    </Link>
                    <span class="notification-action">
                      {{ getActionLabel(item.row_update.action) }}
                    </span>
                    <span
                      v-if="item.row_update.created_by"
                      class="notification-by"
                    >
                      by {{ item.row_update.created_by.title }}
                    </span>
                    <span class="notification-at">
                      {{ formatDateTime(item.row_update.created_at) }}
                    </span>
                  </div>
                  <div
                    v-if="item.row_update.comment_content"
                    class="notification-comment"
                  >
                    <ExpandableCell max-height="10rem">
                      <RenderRawHtml
                        :html="item.row_update.comment_content"
                        className="rich-text-display"
                      />
                    </ExpandableCell>
                  </div>
                  <RowColumnValues
                    v-if="
                      item.row_update.column_values &&
                      item.row_update.column_values.length > 0
                    "
                    :columnValues="item.row_update.column_values"
                    :action="item.row_update.action"
                  />
                </div>
              </div>
            </div>

            <div v-if="p.total_pages > 1" class="notifications-pagination">
              <button
                class="btn btn-sm btn-outline-secondary"
                :disabled="p.current_page <= 1"
                @click="goToPage(p.current_page - 1)"
              >
                Previous
              </button>
              <span class="page-info"
                >Page {{ p.current_page }} of {{ p.total_pages }}</span
              >
              <button
                class="btn btn-sm btn-outline-secondary"
                :disabled="p.current_page >= p.total_pages"
                @click="goToPage(p.current_page + 1)"
              >
                Next
              </button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Layout>
</template>
