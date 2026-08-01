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
        class="git-diff"
      ><code class="hljs language-diff" v-html="rendered"></code></pre>
    </template>
  </Layout>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import Layout from "../components/Layout.vue"
import GitNav from "../components/GitNav.vue"
import { GitDiffPropsSchema } from "../schemas"

const { props } = defineProps<{ props: object }>()
const data = GitDiffPropsSchema.parse(props)

// highlight.js's `diff` grammar colours + / - / @@ lines. Lazily imported so
// marked + highlight.js stay out of the host bundle (same chunk as /files).
const rendered = ref("")
const error = ref(false)
onMounted(async () => {
  if (!data.diff) return
  try {
    const { highlightDiff } = await import("../utils/filePreview")
    rendered.value = highlightDiff(data.diff)
  } catch {
    error.value = true
  }
})
</script>
