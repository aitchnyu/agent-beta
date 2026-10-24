<script setup lang="ts">
// The red error text under a form field. d-block so it shows on its own
// — checkbox groups have no input to flag with is-invalid.
import { computed } from "vue"
import {
  messageFor as catalogMessageFor,
  tryMessageFor,
  type ErrorDetail,
} from "../utils/pydanticErrors"

// message-for overrides copy the catalog doesn't resolve (no template).
const props = defineProps<{
  error?: ErrorDetail | null | undefined
  messageFor?: (_: string) => string
}>()

const text = computed(() => {
  if (!props.error) return ""
  return (
    tryMessageFor(props.error) ??
    props.messageFor?.(props.error.type) ??
    catalogMessageFor(props.error)
  )
})
</script>

<template>
  <div v-if="text" class="invalid-feedback d-block">{{ text }}</div>
</template>
