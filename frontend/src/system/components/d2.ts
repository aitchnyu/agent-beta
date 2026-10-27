// D2 diagram rendering for the /files markdown viewer: fenced ```d2 blocks
// compile and render to SVG through @d2lang/d2 (WASM, own lazy chunk via
// vite.config.js's D2_BUNDLE regex — diagram-free pages fetch none of it,
// the tripwire in test_files.py pins that).
//
// One D2 instance (and its web worker) is kept for the page's lifetime —
// re-creating it per render would reload the ~11.5MB worker every time.
// Compile errors throw with D2's ranged message (file:line:col) — the
// caller (RichTextViewer) catches and shows the raw source deemphasized.

// Memoize the PROMISE, not the instance: a cold page with N fences issues
// N concurrent renders, and instance-memoization let all N pass the null
// check before any assignment — N worker spawns, N-1 orphaned. A failed
// load clears the cache so the next render retries.
import DOMPurify from "dompurify"

let d2Promise: Promise<import("@d2lang/d2").D2> | null = null

function getD2(): Promise<import("@d2lang/d2").D2> {
  if (!d2Promise) {
    d2Promise = import("@d2lang/d2").then(({ D2 }) => new D2())
    // A failed load clears the cache so the next render retries.
    d2Promise.catch(() => {
      d2Promise = null
    })
  }
  return d2Promise
}

export async function renderDiagram(source: string): Promise<string> {
  const d2 = await getD2()
  try {
    // App-level defaults (the WASM build ignores the language's `vars:` block):
    // - layout: elk — tighter packing than dagre on dense graphs
    // - themeID: 1 — Neutral Grey; darkThemeID: 200 — dark mode flips
    //   automatically (d2 embeds the media query in the SVG)
    const result = await d2.compile(source, {
      layout: "elk",
      themeID: 1,
      darkThemeID: 200,
    })
    // One sanitize pass covers the whole app — this is the only path d2
    // output takes into the DOM (it never crosses sanitizeHtml).
    // - d2 escapes every text surface itself
    // - link:/icon: URLs pass schemes through raw — `link: javascript:…`
    //   becomes a clickable <a href>
    // - CSP blocks javascript: URLs on Chromium/Gecko only; WebKit is
    //   unreliable there, so sanitize instead of relying on it
    const svg = await d2.render(result.diagram, result.renderOptions)
    return DOMPurify.sanitize(svg, {
      USE_PROFILES: { svg: true, svgFilters: true },
      ADD_TAGS: ["style"],
      ADD_ATTR: [
        "xlink:href",
        "href",
        "marker-end",
        "mask",
        "class",
        "style",
        "xml:space",
      ],
    })
  } catch (error) {
    // - compile errors carry d2's ranged JSON message; render-stage
    //   diagram errors say "render failed:" — both are source problems,
    //   keep the worker
    // - anything else smells like a dead worker: dispose the old
    //   instance (or it leaks, alive) and drop the cached promise so the
    //   next render rebuilds it
    if (!isDiagramError(error)) {
      d2Promise?.then((d) => d.dispose()).catch(() => {})
      d2Promise = null
    }
    throw error
  }
}

function isDiagramError(error: unknown): boolean {
  const raw = error instanceof Error ? error.message : String(error)
  if (raw.startsWith('render failed:')) return true
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) && parsed[0]?.errmsg !== undefined
  } catch {
    return false
  }
}

// Pan/zoom for rendered diagrams — only the /files markdown viewer enables
// it (RichTextViewer's diagramControls prop).
// - gestures (plain wheel keeps the page scrolling):
//   - ctrl/cmd+wheel zooms
//   - drag pans once zoomed
//   - pinch zooms on touch
// - @panzoom/panzoom rides the d2 chunk (vite.config.js D2_BUNDLE) — no
//   extra request: the chunk is loaded by the time a diagram renders
// - returns the cleanup that unbinds panzoom's document-level move/up
//   listeners — the caller must run it on re-render, or streaming passes
//   stack dead listeners on detached nodes
export async function makeDiagramZoomable(
  container: HTMLDivElement,
): Promise<() => void> {
  const svg = container.querySelector<SVGElement>("svg")
  if (!svg) return () => {}
  const { default: Panzoom } = await import("@panzoom/panzoom")
  const panzoom = Panzoom(svg, {
    maxScale: 8,
    minScale: 1,
    // No `contain`: both modes distort zoom for diagrams whose aspect doesn't
    // match the container — "outside" forces the scale UP until a narrow
    // diagram covers a full-width column, "inside" caps zoom at parent-fit.
    // Free pan instead: drag is enabled only once zoomed, and 1:1 resets.
    panOnlyWhenZoomed: true,
    cursor: "grab",
  })
  container.addEventListener(
    "wheel",
    (event) => {
      if (!(event.ctrlKey || event.metaKey)) return
      event.preventDefault()
      panzoom.zoomWithWheel(event)
    },
    { passive: false },
  )
  const controls = document.createElement("div")
  controls.className = "rich-diagram-controls"
  const buttons: [string, string, string, () => void][] = [
    ["+", "Zoom in", "rich-diagram-zoom-in", () => panzoom.zoomIn()],
    ["−", "Zoom out", "rich-diagram-zoom-out", () => panzoom.zoomOut()],
    ["1:1", "Reset zoom", "rich-diagram-zoom-reset", () => panzoom.reset()],
  ]
  for (const [text, label, extraClass, onClick] of buttons) {
    const button = document.createElement("button")
    button.type = "button"
    button.className = `rich-diagram-zoom ${extraClass}`
    button.textContent = text
    button.title = label
    button.setAttribute("aria-label", label)
    button.addEventListener("click", onClick)
    controls.appendChild(button)
  }
  container.appendChild(controls)
  return () => {
    panzoom.destroy()
    controls.remove()
  }
}
