<script setup lang="ts">
import { ref } from "vue"
import axios from "axios"
import { z } from "zod"
import { ArticleCommentItemSchema } from "../schemas"
import RenderRawHtml from "./RenderRawHtml.vue"
import RichTextEditor from "./RichTextEditor.vue"
import { showErrorToast, showConfirm, showToast } from "../utils/sweetalert"

type ArticleCommentItem = z.infer<typeof ArticleCommentItemSchema>

const props = defineProps<{
  comment: ArticleCommentItem
  canEdit: boolean
  canDelete: boolean
  publicId: string
  pathPrefix: string
}>()

const emit = defineEmits<{
  refreshed: []
}>()

const isEditing = ref(false)
const editContent = ref("")

const formatDateTime = (dateStr: string) => {
  return new Date(dateStr).toLocaleString()
}

const updateUrl = `${props.pathPrefix}/api/${props.publicId}/update-comment/${props.comment.public_id}`
const deleteUrl = `${props.pathPrefix}/api/${props.publicId}/delete-comment/${props.comment.public_id}`

const startEdit = () => {
  isEditing.value = true
  editContent.value = props.comment.content
}

const cancelEdit = () => {
  isEditing.value = false
  editContent.value = ""
}

const saveEdit = async () => {
  if (!editContent.value.trim()) return
  try {
    await axios.post(updateUrl, { content: editContent.value.trim() })
    isEditing.value = false
    editContent.value = ""
    showToast("success", "Comment updated")
    emit("refreshed")
  } catch (e) {
    showErrorToast(e, "Failed to update comment")
  }
}

const deleteComment = async () => {
  const confirmed = await showConfirm({
    title: "Delete comment?",
    text: "This action cannot be undone.",
    confirmButtonText: "Delete",
  })
  if (!confirmed) return
  try {
    await axios.post(deleteUrl)
    showToast("success", "Comment deleted")
    emit("refreshed")
  } catch (e) {
    showErrorToast(e, "Failed to delete comment")
  }
}
</script>

<template>
  <div class="article-comment-item">
    <div class="article-comment-header">
      <div>
        <strong>{{ comment.commented_by.title }}</strong>
        <span class="text-muted ms-2">{{
          formatDateTime(comment.commented_at)
        }}</span>
        <span v-if="comment.updated_at" class="text-muted ms-1">(edited)</span>
      </div>
      <div
        v-if="!isEditing && (canEdit || canDelete)"
        class="article-comment-actions"
      >
        <button
          v-if="canEdit"
          class="btn btn-sm btn-outline-secondary"
          @click="startEdit"
        >
          Edit
        </button>
        <button
          v-if="canDelete"
          class="btn btn-sm btn-outline-danger"
          @click="deleteComment"
        >
          Delete
        </button>
      </div>
    </div>
    <template v-if="isEditing">
      <RichTextEditor v-model="editContent" placeholder="Edit comment..." />
      <div class="mt-1">
        <button class="btn btn-sm btn-primary me-1" @click="saveEdit">
          Save
        </button>
        <button class="btn btn-sm btn-outline-secondary" @click="cancelEdit">
          Cancel
        </button>
      </div>
    </template>
    <template v-else>
      <RenderRawHtml
        :html="comment.content"
        className="article-comment-content rich-text-display"
      />
    </template>
  </div>
</template>
