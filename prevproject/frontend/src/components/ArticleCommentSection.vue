<script setup lang="ts">
import { ref, onMounted } from "vue"
import axios from "axios"
import { z } from "zod"
import {
  ArticleCommentsResponseSchema,
  ArticleCommentItemSchema,
  DeletedArticleCommentItemSchema,
} from "../schemas"
import ActiveArticleComment from "./ActiveArticleComment.vue"
import DeletedArticleComment from "./DeletedArticleComment.vue"
import RichTextEditor from "./RichTextEditor.vue"
import { showErrorToast, showToast } from "../utils/sweetalert"

type ArticleCommentItem = z.infer<typeof ArticleCommentItemSchema>
type DeletedArticleCommentItem = z.infer<typeof DeletedArticleCommentItemSchema>
type CommentItem = ArticleCommentItem | DeletedArticleCommentItem

const props = defineProps<{
  publicId: string
  pathPrefix: string
  canComment: boolean
  canDeleteAny: boolean
  userId: number | null
}>()

const comments = ref<CommentItem[]>([])
const loading = ref(true)
const newContent = ref("")
const submitting = ref(false)

const ONE_HOUR_MS = 60 * 60 * 1000

const commentsUrl = `${props.pathPrefix}/api/comments/${props.publicId}`
const createUrl = `${props.pathPrefix}/api/create-comment/${props.publicId}`

const canEditComment = (comment: ArticleCommentItem) => {
  if (props.userId === null) return false
  if (comment.commented_by.id !== props.userId) return false
  const elapsed = Date.now() - new Date(comment.commented_at).getTime()
  return elapsed <= ONE_HOUR_MS
}

const canDeleteComment = (comment: CommentItem) => {
  if (props.userId !== null && comment.commented_by.id === props.userId)
    return true
  return props.canDeleteAny
}

const fetchComments = async () => {
  try {
    const resp = await axios.get(commentsUrl)
    const data = ArticleCommentsResponseSchema.parse(resp.data)
    comments.value = data.comments
  } catch (e: unknown) {
    showErrorToast(e, "Failed to load comments")
  } finally {
    loading.value = false
  }
}

const submitComment = async () => {
  if (!newContent.value.trim() || submitting.value) return
  submitting.value = true
  try {
    await axios.post(createUrl, { content: newContent.value.trim() })
    newContent.value = ""
    showToast("success", "Comment posted")
    await fetchComments()
  } catch (e) {
    showErrorToast(e, "Failed to post comment")
  } finally {
    submitting.value = false
  }
}

onMounted(fetchComments)
</script>

<template>
  <div class="article-comment-section">
    <h3>Comments</h3>
    <div v-if="loading" class="text-muted">Loading comments...</div>
    <template v-else>
      <div v-if="canComment" class="article-comment-form mb-3">
        <RichTextEditor v-model="newContent" placeholder="Write a comment..." />
        <button
          class="btn btn-primary btn-sm mt-1"
          :disabled="submitting || !newContent.trim()"
          @click="submitComment"
        >
          Post Comment
        </button>
      </div>
      <div v-if="comments.length === 0" class="text-muted mb-3">
        No comments yet.
      </div>
      <template v-for="comment in comments" :key="comment.public_id">
        <ActiveArticleComment
          v-if="!comment.is_deleted"
          :comment="comment"
          :canEdit="canEditComment(comment)"
          :canDelete="canDeleteComment(comment)"
          :publicId="publicId"
          :pathPrefix="pathPrefix"
          @refreshed="fetchComments"
        />
        <DeletedArticleComment v-else :comment="comment" />
      </template>
    </template>
  </div>
</template>
