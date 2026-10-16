<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue"
import MarkdownOutline from "./MarkdownOutline.vue"
import RichTextViewer from "./RichTextViewer.vue"

// The whole markdown preview. Mode is client state only — never in the
// URL, so shared links render identically.
// - rendered mode: outline + rendered HTML
// - source mode: the highlighted source alone
// - owns the async filePreview fill (lazy chunk)
// - owns the scroll-to-hash pass — heading ids exist only after the
//   render, and only rendered mode acts on them
// - emits `rendered` when done, so the parent's [data-files-state]
//   test/a11y hook flips
const props = defineProps<{ text: string; rel: string }>()
const emit = defineEmits<{ rendered: [] }>()

const mode = ref<"rendered" | "source">("rendered")
const rendered = ref("")
// Markdown source shown in source mode (highlighted).
const raw = ref("")
// Heading outline parsed from the final rendered HTML — the ids the renderer
// added are the outline's link targets.
const outline = ref<{ level: number; text: string; id: string }[]>([])

onMounted(async () => {
  // filePreview (hljs/marked) is a lazy chunk; it resolves on first visit.
  const { highlightCode, renderMarkdown } = await import("../utils/filePreview")
  rendered.value = renderMarkdown(props.text, props.rel)
  raw.value = highlightCode(props.text, "markdown")
  // Parse the rendered (sanitized) HTML — outline entries mirror what's on
  // the page, and their ids exist only in that final HTML.
  const doc = new DOMParser().parseFromString(rendered.value, "text/html")
  outline.value = [...doc.querySelectorAll("h1,h2,h3,h4,h5,h6")].map((h) => ({
    level: Number(h.tagName.slice(1)),
    text: h.textContent?.trim() ?? "",
    id: h.id,
  }))
  emit("rendered")
  // Scroll-to-hash: the browser can't do this at load (the ids exist only
  // after the async render), and Inertia navigations skip it too. Wait a
  // tick — the v-html patch that puts the heading ids into the DOM flushes
  // asynchronously, so an immediate getElementById would find nothing.
  if (location.hash) {
    await nextTick()
    document.getElementById(safeFragment(location.hash))?.scrollIntoView()
  }
})

// location.hash without the leading "#", percent-decoded tolerantly — a
// malformed "#%zz" must not throw its way into the error pipeline.
function safeFragment(hash: string): string {
  try {
    return decodeURIComponent(hash.slice(1))
  } catch {
    return hash.slice(1)
  }
}
</script>

<template>
  <div class="files-markdown-toolbar">
    <div class="files-mode-toggle" role="group" aria-label="View mode">
      <button
        type="button"
        class="files-mode-button"
        :class="{ active: mode === 'rendered' }"
        :aria-pressed="mode === 'rendered'"
        @click="mode = 'rendered'"
      >
        Rendered
      </button>
      <button
        type="button"
        class="files-mode-button"
        :class="{ active: mode === 'source' }"
        :aria-pressed="mode === 'source'"
        @click="mode = 'source'"
      >
        Source
      </button>
    </div>
  </div>

  <template v-if="mode === 'rendered'">
    <MarkdownOutline :entries="outline" />
    <!-- RichTextViewer sanitizes again — redundant by design (the HTML here
       is already sanitized + id'd). Kept as defense-in-depth: every
       v-html in the app funnels through one sanitize call site. -->
    <!-- diagram-controls: this component IS the /files markdown view — the
       only RichTextViewer user that zooms (UserDetails/UserHistory render
       it directly, without it). -->
    <RichTextViewer
      class-name="files-markdown"
      :html="rendered"
      diagram-controls
    />
  </template>
  <pre
    v-else
    class="files-code files-raw-source"
  ><code class="hljs language-markdown" v-html="raw"></code></pre>
</template>
