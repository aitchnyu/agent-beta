<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { Link } from "@inertiajs/vue3"
import HumanizedTime from "../components/HumanizedTime.vue"
import PageTitle from "../components/PageTitle.vue"
import RichTextViewer from "../components/RichTextViewer.vue"
import { FileViewerPropsSchema } from "../schemas"
import {
  detectLanguage,
  downloadUrl,
  fileUrl,
  formatSize,
  rawUrl,
} from "../utils/files"

const props = defineProps<{ props: object }>()
const p = FileViewerPropsSchema.parse(props.props)

// A text file renders as syntax-highlighted code when its extension maps to a
// highlight.js language; otherwise it's plain text. Detection is frontend-only.
const codeLang = p.kind === "text" ? detectLanguage(p.name) : undefined

const rendered = ref("")
// Markdown source shown below the rendered view (highlighted).
const raw = ref("")

// Flips when the lazy filePreview chunk has filled rendered/raw. Markdown and
// code previews fill asynchronously; text/image/binary render synchronously.
const previewReady = ref(false)
// Component state for tests (wait on [data-files-state="rendered"] instead of
// polling content magic strings) and a11y (aria-busy while still empty).
const filesState = computed(() =>
  (p.kind === "markdown" || codeLang) && !previewReady.value
    ? "loading"
    : "rendered",
)

onMounted(async () => {
  // filePreview (hljs/marked) is a lazy chunk; it resolves on first visit.
  const { highlightCode, renderMarkdown } = await import("../utils/filePreview")
  if (p.kind === "markdown") {
    rendered.value = renderMarkdown(p.text, p.rel)
    raw.value = highlightCode(p.text, "markdown")
  } else if (codeLang) {
    rendered.value = highlightCode(p.text, codeLang)
  }
  previewReady.value = true
})
</script>

<template>
  <PageTitle :value="p.name" />
  <div
    class="container files-page"
    :data-files-state="filesState"
    :aria-busy="filesState === 'loading'"
  >
    <nav class="files-breadcrumb">
      <template v-for="c in p.breadcrumb" :key="c.rel">
        <Link class="files-crumb" :href="fileUrl(c.rel)">{{ c.label }}</Link>
        <span class="files-sep" aria-hidden="true">/</span>
      </template>
    </nav>
    <div class="files-header">
      <h1 class="files-name">{{ p.name }}</h1>
      <p class="text-muted files-meta">
        {{ formatSize(p.size) }} · {{ p.kind }} ·
        <HumanizedTime :ms="p.mtime" />
      </p>
      <a
        class="btn btn-sm btn-outline-secondary files-download"
        :href="downloadUrl(p.rel)"
        >Download</a
      >
    </div>
    <!-- Markdown: a deemphasized link to the raw source, then the rendered HTML,
           then the raw source (highlighted) as the scroll target. -->
    <template v-if="p.kind === 'markdown'">
      <p class="files-raw-link">
        <a href="#files-raw-source">↓ View raw source</a>
      </p>
      <RichTextViewer class-name="files-markdown" :html="rendered" />
      <pre
        id="files-raw-source"
        class="files-code files-raw-source"
      ><code class="hljs language-markdown" v-html="raw"></code></pre>
    </template>
    <!-- Code: language detected from extension; highlight.js output is escaped. -->
    <pre
      v-else-if="codeLang"
      class="files-code"
    ><code :class="`hljs language-${codeLang}`" v-html="rendered"></code></pre>
    <!-- Plain text: Vue interpolation escapes, so a file's <script> can't run. -->
    <pre v-else-if="p.kind === 'text'" class="files-text">{{ p.text }}</pre>
    <img
      v-else-if="p.kind === 'image'"
      :src="rawUrl(p.rel)"
      :alt="p.name"
      class="files-image"
    />
    <p v-else class="text-muted files-binary">Binary file — not previewable.</p>
  </div>
</template>
