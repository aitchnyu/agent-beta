<script setup lang="ts">
import { computed } from "vue"
import { marked } from "marked"
import { sanitizeHtml } from "../utils/html"

interface Props {
  html?: string | null
  className?: string
  // When true, the input is parsed as markdown before sanitizing (e.g. AI agent
  // replies, which may contain fenced ```code``` blocks → <pre><code>). Default
  // false: the input is already HTML (e.g. from the Quill rich-text editor).
  markdown?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  html: "",
  className: "",
  markdown: false,
})

const sanitizedHtml = computed(() => {
  if (!props.html) return ""
  const source = props.markdown
    ? (marked.parse(props.html, { async: false }) as string)
    : props.html
  return sanitizeHtml(source)
})
</script>

<template>
  <div :class="className" v-html="sanitizedHtml" />
</template>
