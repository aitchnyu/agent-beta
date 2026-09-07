<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue"
import { marked } from "marked"
import { sanitizeHtml } from "../utils/html"
import { renderDiagram } from "../utils/mermaid"

interface Props {
  html?: string | null
  className?: string
  // When true, the input is parsed as markdown before sanitizing (e.g. AI agent
  // replies, which may contain fenced ```code``` blocks → <pre><code>). Default
  // false: the input is already HTML (e.g. from the Quill rich-text editor).
  markdown?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  html: "",
  className: "",
  markdown: false,
})

const root = ref<HTMLElement>()

const sanitizedHtml = computed(() => {
  if (!props.html) return ""
  const source = props.markdown
    ? (marked.parse(props.html, { async: false }) as string)
    : props.html
  return sanitizeHtml(source)
})

// ```mermaid fenced code blocks render to SVG lazily: each <pre> is swapped
// for a .rich-diagram div carrying the SVG (or, on parse failure, the raw
// source styled .rich-diagram-error). The swap is synchronous, so re-runs
// over the same DOM (the sanitizedHtml watcher below) never double-render;
// Vue replaces innerHTML wholesale on each change, so new content always
// gets rendered once.
function renderDiagrams(el: HTMLElement) {
  for (const code of el.querySelectorAll<HTMLElement>(
    "pre > code.language-mermaid",
  )) {
    const pre = code.parentElement
    if (!(pre instanceof HTMLPreElement) || pre.dataset.richRendered) continue
    const source = (code.textContent ?? "").trim()
    if (!source) continue
    pre.dataset.richRendered = "1"
    const div = document.createElement("div")
    div.className = "rich-diagram"
    pre.replaceWith(div)
    renderDiagram(source)
      .then((svg) => {
        div.innerHTML = svg
      })
      .catch(() => {
        // Leave the raw source visible (plain text reads fine) and flag the
        // failure so the stylesheet can deemphasize it.
        div.classList.add("rich-diagram-error")
        div.textContent = source
      })
  }
}

function enrich() {
  const el = root.value
  if (!el) return
  renderDiagrams(el)
}

onMounted(enrich)
// flush:"post" runs after Vue has written the new v-html, so the marker divs are
// in the DOM before we walk them.
watch(sanitizedHtml, enrich, { flush: "post" })
</script>

<template>
  <div ref="root" :class="className" v-html="sanitizedHtml" />
</template>
