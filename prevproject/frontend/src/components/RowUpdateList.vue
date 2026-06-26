<script setup lang="ts">
import { ref, computed, onMounted, type PropType } from "vue"
import { z } from "zod"
import axios from "axios"
import { showErrorToast, showToast, showConfirm } from "../utils/sweetalert"
import {
  RowUpdateResponseSchema,
  RowUpdateListResponseSchema,
} from "../schemas"
import RowUpdateComment from "./RowUpdateComment.vue"
import RowColumnValues from "./RowColumnValues.vue"
import CommentForm from "./CommentForm.vue"
import { formatDateTime, getActionLabel } from "../utils/rowUpdate"

type RowUpdateItem = z.infer<typeof RowUpdateResponseSchema>

const props = defineProps({
  viewname: {
    type: String as PropType<string>,
    required: true,
  },
  rowId: {
    type: String as PropType<string>,
    required: true,
  },
  currentUsername: {
    type: String as PropType<string | null>,
    default: null,
  },
})

const rowUpdates = ref<RowUpdateItem[]>([])
const isLoading = ref(true)
const hasError = ref(false)
const canCreateComment = ref(false)
const editCommentTimeout = ref(0)
const deleteCommentTimeout = ref(0)

const fetchRowUpdates = async () => {
  isLoading.value = true
  try {
    const response = await axios.get(
      `/tables/api/${props.viewname}/row-updates/${props.rowId}`,
    )
    const parsed = RowUpdateListResponseSchema.parse(response.data)
    canCreateComment.value = parsed.can_create_comment
    editCommentTimeout.value = parsed.edit_comment_timeout ?? 0
    deleteCommentTimeout.value = parsed.delete_comment_timeout ?? 0
    rowUpdates.value = parsed.updates
  } catch (e: unknown) {
    showErrorToast(e, "Failed to load row updates")
    hasError.value = true
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchRowUpdates)

defineExpose({ fetchRowUpdates })

const handleDeleteComment = async (rowUpdateId: string) => {
  const confirmed = await showConfirm({
    title: "Delete comment?",
    text: "The comment content will be permanently removed.",
    confirmButtonText: "Yes, delete it",
  })

  if (confirmed) {
    try {
      await axios.post(
        `/tables/api/${props.viewname}/${props.rowId}/delete-comment/${rowUpdateId}`,
      )
      showToast("success", "Comment deleted")
      await fetchRowUpdates()
    } catch (e: unknown) {
      showErrorToast(e, "Failed to delete comment.")
    }
  }
}

const handleEditComment = async (rowUpdateId: string, newContent: string) => {
  try {
    await axios.post(
      `/tables/api/${props.viewname}/${props.rowId}/update-comment/${rowUpdateId}`,
      { comment_content: newContent },
    )
    showToast("success", "Comment updated")
    await fetchRowUpdates()
  } catch (e: unknown) {
    showErrorToast(e, "Failed to update comment. You may not have permission.")
  }
}

type FilterMode = "all" | "comments" | "updates"
const filterMode = ref<FilterMode>("all")

const filteredUpdates = computed(() => {
  if (filterMode.value === "all") {
    return rowUpdates.value
  }
  if (filterMode.value === "comments") {
    return rowUpdates.value.filter((u) => u.action === "commented")
  }
  return rowUpdates.value.filter((u) => u.action !== "commented")
})
</script>

<template>
  <div class="row-update-container">
    <div v-if="isLoading" class="row-updates-loading">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
      <span class="ms-2">Loading updates...</span>
    </div>

    <div v-else-if="!hasError" class="row-update-list">
      <div class="row-update-header">
        <h4>History</h4>
        <div class="filter-buttons">
          <button
            @click="filterMode = 'all'"
            class="filter-btn"
            :class="{ active: filterMode === 'all' }"
          >
            All
          </button>
          <button
            @click="filterMode = 'comments'"
            class="filter-btn"
            :class="{ active: filterMode === 'comments' }"
          >
            Comments
          </button>
          <button
            @click="filterMode = 'updates'"
            class="filter-btn"
            :class="{ active: filterMode === 'updates' }"
          >
            Updates
          </button>
        </div>
      </div>

      <CommentForm
        v-if="canCreateComment"
        :viewname="viewname"
        :rowId="rowId"
        @comment-added="fetchRowUpdates"
      />

      <div v-if="filteredUpdates.length === 0" class="no-updates">
        No updates to display
      </div>

      <div v-else class="updates-timeline">
        <div
          v-for="update in filteredUpdates"
          :key="update.id"
          class="update-item"
          :class="`action-${update.action}`"
        >
          <div class="update-meta">
            <span class="update-action">{{
              getActionLabel(update.action)
            }}</span>
            <span v-if="update.created_by" class="update-by"
              >by {{ update.created_by.title }}</span
            >
            <span class="update-at">{{
              formatDateTime(update.created_at)
            }}</span>
          </div>

          <div v-if="update.action === 'commented'" class="comment-content">
            <RowUpdateComment
              :update="update"
              :edit-comment-timeout="editCommentTimeout"
              :delete-comment-timeout="deleteCommentTimeout"
              :currentUsername="currentUsername"
              @delete-comment="handleDeleteComment"
              @edit-comment="handleEditComment"
            />
          </div>

          <RowColumnValues
            v-if="update.column_values && update.column_values.length > 0"
            :columnValues="update.column_values"
            :action="update.action"
          />
        </div>
      </div>
    </div>
  </div>
</template>
