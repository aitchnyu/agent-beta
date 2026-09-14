<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { Link } from "@inertiajs/vue3"
import HumanizedTime from "../components/HumanizedTime.vue"
import MarkdownView from "../components/MarkdownView.vue"
import PageTitle from "../components/PageTitle.vue"
import RepoNav from "../components/RepoNav.vue"
import { FileViewerPropsSchema } from "../schemas"
import {
  detectLanguage,
  downloadUrl,
  fileUrl,
  formatSize,
  rawUrl,
} from "../utils/files"

const props = defineProps<{ props: object }>()
// Parsed once, non-reactively: file→file navigation is always a full page
// load in this app (v-html anchors aren't Inertia links), so the component
// never receives new props in place. Inertia re-keys the page component on
// every visit, remounting this with fresh props.
const p = FileViewerPropsSchema.parse(props.props)

// A text file renders as syntax-highlighted code when its extension maps to a
// highlight.js language; otherwise it's plain text. Detection is frontend-only.
const codeLang = p.kind === "text" ? detectLanguage(p.name) : undefined

// Code previews fill asynchronously (lazy filePreview chunk); MarkdownView
// flips this via its `rendered` emit. Text/image/binary render synchronously.
const rendered = ref("")
const previewReady = ref(false)
// Component state for tests (wait on [data-files-state="rendered"] instead of
// polling content magic strings) and a11y (aria-busy while still empty).
const filesState = computed(() =>
  (p.kind === "markdown" || codeLang) && !previewReady.value
    ? "loading"
    : "rendered",
)

onMounted(async () => {
  if (!codeLang) return
  // filePreview (hljs/marked) is a lazy chunk; it resolves on first visit.
  const { highlightCode } = await import("../utils/filePreview")
  rendered.value = highlightCode(p.text, codeLang)
  previewReady.value = true
})
</script>

<template>
  <PageTitle :value="p.name" />
  <div :data-files-state="filesState" :aria-busy="filesState === 'loading'">
    <RepoNav />
    <nav class="files-breadcrumb">
      <template v-for="c in p.breadcrumb" :key="c.rel">
        <Link class="files-crumb" :href="fileUrl(c.rel)">{{ c.label }}</Link>
        <span class="files-sep" aria-hidden="true">/</span>
      </template>
    </nav>
    <div class="files-header">
      <h3 class="files-name">{{ p.name }}</h3>
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
