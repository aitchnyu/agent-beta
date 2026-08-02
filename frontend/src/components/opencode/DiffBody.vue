<script setup lang="ts">
import { ref, watch } from "vue"

// Renders an old→new edit as a unified diff coloured by highlight.js's `diff`
// grammar. Both the diff computation (jsdiff) and the highlighter (hljs) are
// lazy-imported so neither lands in the host bundle.
const props = defineProps<{ old: string; new: string }>()

const rendered = ref("")
const error = ref(false)

async function render() {
  // Clear any prior failure so a later successful render recovers.
  error.value = false
  try {
    // jsdiff computes a unified patch; strip the Index/---/+++ header (keep from
    // the first @@) and skip entirely when there's no hunk (identical input).
    // Both jsdiff and the hljs highlighter are lazy-imported so neither lands in
    // the host bundle.
    const { createPatch } = await import("diff")
    const { highlightDiff } = await import("../../utils/filePreview")
    const patch = createPatch("file", props.old, props.new, "", "", {
      context: 3,
    })
    const at = patch.indexOf("@@")
    if (at < 0) {
      rendered.value = ""
      return
    }
    rendered.value = highlightDiff(patch.slice(at))
  } catch {
    // A non-string old/new (malformed wire data) throws in jsdiff, or the
    // dynamic import fails — surface it as the error state, not an unhandled
    // rejection with the diff silently blank.
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
