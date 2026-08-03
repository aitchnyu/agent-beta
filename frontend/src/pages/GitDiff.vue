<template>
  <Layout>
    <GitNav />
    <h1>{{ data.title }}</h1>
    <p v-if="error" class="text-danger">Failed to render diff.</p>
    <template v-else-if="!data.diff">
      <p class="text-muted">No changes.</p>
    </template>
    <template v-else>
      <p v-if="!rendered" class="text-muted">Loading…</p>
      <pre
        v-else
        class="code-diff"
      ><code class="hljs language-diff" v-html="rendered"></code></pre>
    </template>
  </Layout>
</template>

<script setup lang="ts">
import { ref } from "vue"
import Layout from "../components/Layout.vue"
import GitNav from "../components/GitNav.vue"
import { GitDiffPropsSchema } from "../schemas"
import { highlightDiff } from "../utils/filePreview"

const props = defineProps<{ props: object }>()
const data = GitDiffPropsSchema.parse(props.props)

// Eager import (NOT a dynamic import in onMounted): firing a dynamic import
// during an Inertia v2 swap makes Inertia silently roll the navigation back, so
// the highlighter is imported at module load. highlight.js ships in main.js
// alongside this page.
const rendered = ref("")
const error = ref(false)
try {
  if (data.diff) rendered.value = highlightDiff(data.diff)
} catch {
  error.value = true
}
</script>
