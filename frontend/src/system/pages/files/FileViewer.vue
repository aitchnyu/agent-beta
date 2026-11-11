<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { Link } from "@inertiajs/vue3"
import HumanizedTime from "../../components/HumanizedTime.vue"
import MarkdownView from "../../components/files/MarkdownView.vue"
import PageTitle from "../../components/PageTitle.vue"
import { FileViewerPropsSchema } from "../../schemas/files"
import { useAppPage } from "../../utils/useAppPage"
import {
  detectLanguage,
  downloadUrl,
  fileUrl,
  formatSize,
  rawUrl,
} from "./files"

// file→file navigation is always a full page load in this app (v-html
// anchors aren't Inertia links), so this component remounts with fresh
// props on every visit.
const { data: p } = useAppPage(FileViewerPropsSchema)

// A text file renders as syntax-highlighted code when its extension maps to a
// highlight.js language; otherwise it's plain text. Detection is frontend-only.
const codeLang =
  p.value.kind === "text" ? detectLanguage(p.value.name) : undefined

// Code previews fill asynchronously (lazy filePreview chunk); MarkdownView
// flips this via its `rendered` emit. Text/image/binary render synchronously.
const rendered = ref("")
const previewReady = ref(false)

// Plain text renders one span per line so CSS counters can number them
// (.files-line::before) — no gutter element to keep in sync. A single
// trailing newline is the file's terminator, not a line: strip it (an
// empty file renders no rows at all).
const textLines = computed(() =>
  p.value.text === "" ? [] : p.value.text.replace(/\n$/, "").split("\n"),
)
// Component state for tests (wait on [data-files-state="rendered"] instead of
// polling content magic strings) and a11y (aria-busy while still empty).
const filesState = computed(() =>
  (p.value.kind === "markdown" || codeLang) && !previewReady.value
    ? "loading"
    : "rendered",
)

onMounted(async () => {
  if (!codeLang) return
  // filePreview (hljs/marked) is a lazy chunk; it resolves on first visit.
  const { highlightCode } = await import("./filePreview")
  rendered.value = highlightCode(p.value.text, codeLang)
  previewReady.value = true
})
</script>

<template>
  <PageTitle :value="p.name" />
  <div :data-files-state="filesState" :aria-busy="filesState === 'loading'">
    <nav class="files-breadcrumb">
      <template v-for="c in p.breadcrumb" :key="c.rel">
        <Link class="files-crumb" :href="fileUrl(c.rel)">{{ c.label }}</Link>
        <span class="files-separator" aria-hidden="true">/</span>
      </template>
    </nav>
    <div class="files-header">
      <h3 class="files-name">{{ p.name }}</h3>
      <p class="text-muted files-meta">
        {{ formatSize(p.size) }} · {{ p.kind }} ·
        <HumanizedTime :ms="p.mtime" absolute />
      </p>
      <a
        class="btn btn-sm btn-outline-secondary files-download"
        :href="downloadUrl(p.rel)"
        >Download</a
      >
    </div>
    <!-- Markdown: the whole preview (outline, rendered HTML, raw source) lives
            in MarkdownView; it flips this page's files-state via `rendered`. -->
    <MarkdownView
      v-if="p.kind === 'markdown'"
      :key="p.rel"
      :text="p.text"
      :rel="p.rel"
      @rendered="previewReady = true"
    />
    <!-- Code: language detected from extension; highlight.js output is escaped. -->
    <pre
      v-else-if="codeLang"
      class="files-code"
    ><code :class="`hljs language-${codeLang}`" v-html="rendered"></code></pre>
    <!-- Plain text: one span per line, numbered by CSS counters. Vue
             interpolation escapes each line, so a file's <script> can't run. -->
    <div v-else-if="p.kind === 'text'" class="files-text">
      <span v-for="(line, i) in textLines" :key="i" class="files-line">{{
        line
      }}</span>
    </div>
    <img
      v-else-if="p.kind === 'image'"
      :src="rawUrl(p.rel)"
      :alt="p.name"
      class="files-image"
    />
    <p v-else class="text-muted files-binary">Binary file — not previewable.</p>
  </div>
</template>
