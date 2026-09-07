<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue"
import MarkdownOutline from "./MarkdownOutline.vue"
import RichTextViewer from "./RichTextViewer.vue"

// The whole markdown preview: heading outline at the top, a deemphasized link
// to the raw source, the rendered HTML, then the highlighted raw source (the
// #files-raw-source scroll target). Owns the async filePreview fill (lazy
// chunk) and the scroll-to-hash pass (heading ids exist only after the
// render); emits `rendered` when done so the parent's
// [data-files-state] test/a11y hook flips.
const props = defineProps<{ text: string; rel: string }>()
const emit = defineEmits<{ rendered: [] }>()

const rendered = ref("")
// Markdown source shown below the rendered view (highlighted).
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
  <MarkdownOutline :entries="outline" />
  <p class="files-raw-link">
    <a href="#files-raw-source">↓ View raw source</a>
  </p>
  <!-- RichTextViewer sanitizes again — redundant by design (the HTML here is
     already sanitized + id'd) and kept as defense-in-depth: every v-html in
     the app funnels through one sanitize call site. -->
  <RichTextViewer class-name="files-markdown" :html="rendered" />
  <pre
    id="files-raw-source"
    class="files-code files-raw-source"
  ><code class="hljs language-markdown" v-html="raw"></code></pre>
</template>
