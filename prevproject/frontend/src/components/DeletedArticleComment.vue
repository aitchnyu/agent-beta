<script setup lang="ts">
import { z } from "zod"
import { DeletedArticleCommentItemSchema } from "../schemas"

type DeletedArticleCommentItem = z.infer<typeof DeletedArticleCommentItemSchema>

defineProps<{
  comment: DeletedArticleCommentItem
}>()

const formatDateTime = (dateStr: string) => {
  return new Date(dateStr).toLocaleString()
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
      </div>
    </div>
    <div class="article-comment-deleted">[deleted]</div>
  </div>
</template>
