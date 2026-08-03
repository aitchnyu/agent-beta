<script setup lang="ts">
import { ref, watch } from "vue"
import { unifiedHunk } from "../../utils/diff"

// Renders an old→new edit as a unified diff coloured by highlight.js's `diff`
// grammar. Both heavy deps are lazy chunks kept out of the host bundle: jsdiff
// inside utils/diff, and hljs via utils/filePreview (pre-warmed at boot in
// main.ts). 
const props = defineProps<{ old: string; new: string }>()

const rendered = ref("")
const error = ref(false)

async function render() {
  // Clear any prior failure so a later successful render recovers.
  error.value = false
  try {
    const hunk = await unifiedHunk(props.old, props.new)
    if (hunk === null) {
      rendered.value = ""
      return
    }
    const { highlightDiff } = await import("../../utils/filePreview")
    rendered.value = highlightDiff(hunk)
  } catch {
    // A non-string old/new (malformed wire data) throws in jsdiff, or the lazy
    // import fails — surface it as the error state, not an unhandled rejection
    // with the diff silently blank.
    error.value = true
  }
}

watch(() => [props.old, props.new], render, { immediate: true })
</script>

<template>
  <p v-if="error" class="opencode-tool-body text-danger">
    Failed to render diff.
  </p>
  <pre v-else-if="rendered" class="opencode-tool-body code-diff"><code
    class="hljs language-diff"
    v-html="rendered"
  ></code></pre>
</template>
