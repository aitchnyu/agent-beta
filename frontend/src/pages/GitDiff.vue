<template>
  <Layout>
    <PageTitle :value="data.title" />
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
import { onMounted, ref } from "vue"
import Layout from "../components/Layout.vue"
import PageTitle from "../components/PageTitle.vue"
import GitNav from "../components/GitNav.vue"
import { GitDiffPropsSchema } from "../schemas"

const props = defineProps<{ props: object }>()
const data = GitDiffPropsSchema.parse(props.props)

// The highlighter (hljs, via utils/filePreview) is a lazy chunk kept OUT of
// main.js. It's imported here in onMounted (not in setup) after pre-warm has
// cached the chunk in main.ts — a cold dynamic import during an Inertia v2 swap
// rolls the navigation back, but a cache-hit resolves in a microtask, no gap.
const rendered = ref("")
const error = ref(false)
onMounted(async () => {
  try {
    if (data.diff) {
      const { highlightDiff } = await import("../utils/filePreview")
      rendered.value = highlightDiff(data.diff)
    }
  } catch {
    error.value = true
  }
})
</script>
