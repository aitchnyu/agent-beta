<script setup lang="ts">
import { onMounted, ref } from "vue"
import type { Diff2HtmlUIConfig } from "diff2html/lib-esm/ui/js/diff2html-ui-base.js"
import { EXTENSION_TO_LANGUAGE } from "../../pages/files/files"

const props = defineProps<{ diff: string }>()

// One container per outputFormat of the same diff (side-by-side +
// line-by-line), shown/hidden by the 992px media query in _files.scss —
// diff2html has no responsive format switching of its own. CSS-only toggling
// keeps the Playwright viewport test deterministic (no resize listeners).
const sideEl = ref<HTMLElement>()
const lineEl = ref<HTMLElement>()
const ready = ref(false)
const failed = ref(false)

// diff2html's generated markup carries template whitespace: newlines
// between the prefix and content spans, and a trailing newline inside
// every line element (copy-paste friendly under the package's pre
// layout). Under pre-wrap that whitespace renders as real breaks and
// blank rows — strip pure-newline text nodes and trailing newlines so
// only genuine line content remains, and long lines wrap instead of
// blowing rows up.
function normalizeDiffWhitespace(root: HTMLElement) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const nodes: Text[] = []
  while (walker.nextNode()) nodes.push(walker.currentNode as Text)
  for (const node of nodes) {
    const value = node.nodeValue ?? ""
    if (!value.includes("\n") && !value.includes("\r")) continue
    if (!value.trim()) {
      node.remove() // pure template separator
      continue
    }
    node.nodeValue = value.replace(/\r?\n$/, "") // drop one trailing newline
  }
}

onMounted(async () => {
  // diff2html (+ its CSS) and the shared hljs instance are lazy chunks; the
  // "Loading…" note shows until `ready` flips, the error note if they fail
  // to load (a stuck Loading state would be worse).
  try {
    const [{ Diff2HtmlUI }, { getHighlighter }] = await Promise.all([
      import("diff2html/lib-esm/ui/js/diff2html-ui-base.js"),
      import("../../pages/files/filePreview"),
      import("diff2html/bundles/css/diff2html.min.css"),
    ])
    const base: Diff2HtmlUIConfig = {
      drawFileList: false, // one file per page; the page h1 already names it
      fileContentToggle: false,
      stickyFileHeaders: false,
      highlight: true, // draw() runs highlightCode itself
      diffStyle: "word", // intra-line word-level highlighting
      matching: "none",
      // Extension→language for content highlighting (vue→xml etc.) — diff2html's
      // own map misses app-specific extensions.
      highlightLanguages: new Map([
        ...Object.entries(EXTENSION_TO_LANGUAGE),
        ["md", "markdown"],
      ]),
    }
    const hljs = getHighlighter()
    // draw() applies each config flag (highlight, synchronisedScroll) — calling
    // those methods again on top would re-highlight every line and attach
    // duplicate scroll listeners.
    new Diff2HtmlUI(
      sideEl.value!,
      props.diff,
      { ...base, outputFormat: "side-by-side", synchronisedScroll: true },
      hljs,
    ).draw()
    new Diff2HtmlUI(
      lineEl.value!,
      props.diff,
      { ...base, outputFormat: "line-by-line" },
      hljs,
    ).draw()
    normalizeDiffWhitespace(sideEl.value!)
    normalizeDiffWhitespace(lineEl.value!)
    ready.value = true
  } catch {
    failed.value = true
  }
})
</script>

<template>
  <div class="diff-view d2h-auto-color-scheme" data-split-diff>
    <p v-if="failed" class="text-danger">Failed to render diff.</p>
    <p v-else-if="!ready" class="text-muted">Loading…</p>
    <!-- The side-by-side container holds BOTH panes (diff2html's own columns). -->
    <div v-show="ready" ref="sideEl" data-split-diff-side></div>
    <div v-show="ready" ref="lineEl" data-split-diff-unified></div>
  </div>
</template>
