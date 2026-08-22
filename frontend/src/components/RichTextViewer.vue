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

// `.rich-mockup` holds view-only Bootstrap markup: strip every link/form
// action and disable all controls so the preview can't navigate or submit.
function neuterMockups(el: HTMLElement) {
  for (const box of el.querySelectorAll<HTMLElement>(".rich-mockup")) {
    box.querySelectorAll("a").forEach((a) => a.removeAttribute("href"))
    box.querySelectorAll("form").forEach((f) => f.removeAttribute("action"))
    box
      .querySelectorAll("button, input, select, textarea")
      .forEach((c) => ((c as HTMLInputElement).disabled = true))
  }
}

// `.rich-diagram` holds raw Mermaid source; render it to SVG lazily. Mark
// the node so a re-run over the same DOM (onUpdated) doesn't kick off a second
// render; Vue replaces innerHTML wholesale on each change, so new content is
// always fresh and gets rendered once.
function renderDiagrams(el: HTMLElement) {
  for (const node of el.querySelectorAll<HTMLElement>(".rich-diagram")) {
    if (node.dataset.richRendered) continue
    const source = (node.textContent ?? "").trim()
    if (!source) continue
    node.dataset.richRendered = "1"
    renderDiagram(source)
      .then((svg) => {
        node.innerHTML = svg
      })
      .catch(() => {
        // Leave the raw source visible (it already reads as plain text) and flag
        // the failure so the stylesheet can deemphasize it.
        node.classList.add("rich-diagram-error")
      })
  }
}

function enrich() {
  const el = root.value
  if (!el) return
  neuterMockups(el)
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
