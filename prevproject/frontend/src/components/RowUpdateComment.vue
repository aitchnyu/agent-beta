<script setup lang="ts">
import { ref, computed, type PropType } from "vue"
import { z } from "zod"
import { RowUpdateResponseSchema } from "../schemas"
import RichTextEditor from "./RichTextEditor.vue"
import RenderRawHtml from "./RenderRawHtml.vue"
import ExpandableCell from "./ExpandableCell.vue"

type RowUpdateItem = z.infer<typeof RowUpdateResponseSchema>

const props = defineProps({
  update: {
    type: Object as PropType<RowUpdateItem>,
    required: true,
  },
  editCommentTimeout: {
    type: Number as PropType<number>,
    default: 1,
  },
  deleteCommentTimeout: {
    type: Number as PropType<number>,
    default: 0,
  },
  currentUsername: {
    type: String as PropType<string | null>,
    default: null,
  },
})

const emit = defineEmits<{
  "delete-comment": [rowUpdateId: string]
  "edit-comment": [rowUpdateId: string, newContent: string]
}>()

const isEditing = ref(false)
const editContent = ref("")

const formatDateTime = (dateStr: string) => {
  return new Date(dateStr).toLocaleString()
}

const canDelete = computed(() => {
  if (props.deleteCommentTimeout <= 0) {
    return false
  }
  const createdAt = new Date(props.update.created_at)
  const timeoutMs = props.deleteCommentTimeout * 1000
  const absoluteTimeout = new Date(createdAt.getTime() + timeoutMs)
  const now = new Date()

  return (
    props.update.action === "commented" &&
    !props.update.comment_deleted_at &&
    now < absoluteTimeout
  )
})

const canEdit = computed(() => {
  if (props.editCommentTimeout <= 0) {
    return false
  }
  const createdAt = new Date(props.update.created_at)
  const timeoutMs = props.editCommentTimeout * 1000
  const absoluteTimeout = new Date(createdAt.getTime() + timeoutMs)
  const now = new Date()

  return (
    props.update.action === "commented" &&
    !props.update.comment_deleted_at &&
    now < absoluteTimeout
  )
})

const startEdit = () => {
  isEditing.value = true
  editContent.value = props.update.comment_content || ""
}

const cancelEdit = () => {
  isEditing.value = false
  editContent.value = ""
}

const saveEdit = () => {
  if (editContent.value.trim()) {
    emit("edit-comment", props.update.id, editContent.value.trim())
    isEditing.value = false
    editContent.value = ""
  }
}

const handleDelete = () => {
  emit("delete-comment", props.update.id)
}
</script>

<template>
  <div class="comment-content">
    <template v-if="update.comment_deleted_at">
      <em class="comment-deleted">[Comment deleted]</em>
    </template>
    <template v-else-if="isEditing">
      <div class="edit-comment-form">
        <RichTextEditor v-model="editContent" />
        <div class="edit-comment-buttons">
          <button @click="saveEdit" class="save-edit-btn">Save</button>
          <button @click="cancelEdit" class="cancel-edit-btn">Cancel</button>
        </div>
      </div>
    </template>
    <template v-else>
      <div class="comment-display">
        <ExpandableCell max-height="10rem">
          <RenderRawHtml
            :html="update.comment_content ?? ''"
            className="rich-text-display"
          />
        </ExpandableCell>
        <span
          v-if="update.edited_by && update.edited_at"
          class="comment-edited-indicator"
        >
          (edited by {{ update.edited_by.title }} at
          {{ formatDateTime(update.edited_at) }})
        </span>
        <div v-if="canEdit || canDelete" class="comment-actions">
          <button v-if="canEdit" @click="startEdit" class="edit-comment-btn">
            Edit
          </button>
          <button
            v-if="canDelete"
            @click="handleDelete"
            class="delete-comment-btn"
          >
            Delete
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
