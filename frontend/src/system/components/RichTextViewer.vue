<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { marked } from "marked"
import { sanitizeHtml } from "./html"
import { renderDiagram, makeDiagramZoomable } from "./d2"

interface Props {
  html?: string | null
  className?: string
  // When true, the input is parsed as markdown before sanitizing (e.g. AI agent
  // replies, which may contain fenced ```code``` blocks → <pre><code>). Default
  // false: the input is already HTML (e.g. from the Quill rich-text editor).
  markdown?: boolean
  // Pan/zoom controls on rendered d2 diagrams. Only the /files markdown
  // viewer enables it; the other RichTextViewer users (UserDetails,
  // UserHistory) stay static — no controls, no panzoom wiring.
  diagramControls?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  html: "",
  className: "",
  markdown: false,
  diagramControls: false,
})

const root = ref<HTMLElement>()

const sanitizedHtml = computed(() => {
  if (!props.html) return ""
  const source = props.markdown
    ? (marked.parse(props.html, { async: false }) as string)
    : props.html
  return sanitizeHtml(source)
})

// ```d2 fenced code blocks render to SVG lazily: each <pre> is swapped
// for a .rich-diagram div carrying the SVG (or, on parse failure, the raw
// source styled .rich-diagram-error). The swap is synchronous, so re-runs
// over the same DOM (the sanitizedHtml watcher below) never double-render;
// Vue replaces innerHTML wholesale on each change, so new content always
// gets rendered once.
// Zoom instances bind document-level move/up listeners, so a re-render that
// replaces the DOM would orphan them — destroy the previous batch here, right
// before the fresh render starts stacking new ones. Same on unmount.
const zoomCleanups: (() => void)[] = []

// One fence: swap its <pre> for a .rich-diagram div and fill it. Fire-and-
// forget from enrich() — each fence renders independently.
async function renderFence(div: HTMLDivElement, source: string) {
  try {
    const svg = await renderDiagram(source)
    // Toggled away mid-render (unmount) — the div is detached; wiring
    // panzoom on it would leak document-level listeners no cleanup ever
    // drains (the unmount hook already ran on an empty list).
    if (!div.isConnected) return
    div.innerHTML = svg
    if (props.diagramControls) {
      try {
        const cleanup = await makeDiagramZoomable(div)
        zoomCleanups.push(cleanup)
      } catch {
        // Controls are optional by design: if the panzoom module failed
        // to load, the rendered diagram still shows.
      }
    }
  } catch {
    // Leave the raw source visible (plain text reads fine) and flag the
    // failure so the stylesheet can deemphasize it.
    div.classList.add("rich-diagram-error")
    div.textContent = source
  }
}

function renderDiagrams(el: HTMLElement) {
  for (const code of el.querySelectorAll<HTMLElement>(
    "pre > code.language-d2",
  )) {
    const pre = code.parentElement
    if (!(pre instanceof HTMLPreElement) || pre.dataset.richRendered) continue
    const source = (code.textContent ?? "").trim()
    if (!source) continue
    pre.dataset.richRendered = "1"
    const div = document.createElement("div")
    div.className = "rich-diagram"
    pre.replaceWith(div)
    renderFence(div, source)
  }
}

function enrich() {
  const el = root.value
  if (!el) return
  for (const cleanup of zoomCleanups.splice(0)) cleanup()
  renderDiagrams(el)
}

onMounted(enrich)
onBeforeUnmount(() => {
  for (const cleanup of zoomCleanups.splice(0)) cleanup()
})
// flush:"post" runs after Vue has written the new v-html, so the marker divs are
// in the DOM before we walk them.
watch(sanitizedHtml, enrich, { flush: "post" })
</script>

<template>
  <div ref="root" :class="className" v-html="sanitizedHtml" />
</template>
