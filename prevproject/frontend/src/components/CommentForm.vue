<script setup lang="ts">
import { ref, computed } from "vue"
import axios from "axios"
import RichTextEditor from "./RichTextEditor.vue"
import { showErrorToast } from "../utils/sweetalert"

const MAX_COMMENT_LENGTH = 1000

const props = defineProps<{
  viewname: string
  rowId: string
}>()

const emit = defineEmits<{
  "comment-added": []
}>()

const comment = ref("")
const isSubmitting = ref(false)
const errorMessage = ref<string | null>(null)

const remainingChars = computed(() => {
  return MAX_COMMENT_LENGTH - comment.value.length
})

const isOverLimit = computed(() => {
  return comment.value.length > MAX_COMMENT_LENGTH
})

const canSubmit = computed(() => {
  return (
    comment.value.trim().length > 0 && !isOverLimit.value && !isSubmitting.value
  )
})

const submitComment = async () => {
  if (!canSubmit.value) {
    return
  }

  isSubmitting.value = true
  errorMessage.value = null

  try {
    await axios.post(
      `/tables/api/${props.viewname}/create-comment/${props.rowId}`,
      {
        comment_content: comment.value.trim(),
      },
    )
    comment.value = ""
    emit("comment-added")
  } catch (e: unknown) {
    showErrorToast(e, "Failed to add comment")
    errorMessage.value = "Failed to add comment. Please try again."
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="comment-form">
    <h4>Add Comment</h4>
    <div class="comment-input-wrapper">
      <RichTextEditor v-model="comment" placeholder="Add a comment..." />
      <div class="char-counter" :class="{ 'over-limit': isOverLimit }">
        {{ remainingChars }} characters remaining
      </div>
    </div>
    <div v-if="errorMessage" class="error-message">
      {{ errorMessage }}
    </div>
    <button @click="submitComment" :disabled="!canSubmit" class="submit-btn">
      {{ isSubmitting ? "Submitting..." : "Submit" }}
    </button>
  </div>
</template>
