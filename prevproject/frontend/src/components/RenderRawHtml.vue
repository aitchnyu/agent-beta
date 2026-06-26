<script setup lang="ts">
import { computed } from "vue"
import { sanitizeHtml } from "../utils/html"

interface Props {
  html?: string | null
  className?: string
}

const props = withDefaults(defineProps<Props>(), {
  html: "",
  className: "",
})

const sanitizedHtml = computed(() =>
  props.html ? sanitizeHtml(props.html) : "",
)
</script>

<template>
  <div :class="className" v-html="sanitizedHtml" />
</template>
