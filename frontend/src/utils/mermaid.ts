// Lazy Mermaid rendering for `.opencode-diagram` blocks. Mermaid is large
// (~2.5 MB), so it is dynamically imported on first use and stays a separate
// chunk out of the main bundle. The module-level promise caches both the import
// and the one-time initialize(), so repeated diagrams pay the cost only once.
//
// securityLevel "strict" makes Mermaid strip raw HTML from labels (labels
// already avoid <>& per steer.md) and disables click bindings, keeping diagrams
// view-only and safe inside sanitized HTML.
import type { Mermaid } from "mermaid"

let mermaidPromise: Promise<Mermaid> | null = null

function getMermaid(): Promise<Mermaid> {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then((mod) => {
      const mermaid = mod.default
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "base",
        themeVariables: {
          fontFamily:
            'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
          fontSize: "14px",
          primaryColor: "#eff6ff", // blue-50-ish node fill
          primaryBorderColor: "#2563eb", // $blue-600
          primaryTextColor: "#1f2937", // $gray-800
          lineColor: "#6b7280", // $gray-500
          secondaryColor: "#f3f4f6", // $gray-100
          tertiaryColor: "#f9fafb", // $gray-50
          textColor: "#1f2937",
        },
      })
      return mermaid
    })
  }
  return mermaidPromise
}

let idSeq = 0

/** Render Mermaid source to an SVG string. Rejects on a parse error so the
 *  caller can fall back to showing the raw source. */
export async function renderDiagram(source: string): Promise<string> {
  const mermaid = await getMermaid()
  const id = `opencode-mermaid-${idSeq++}`
  // mermaid.render appends a throwaway <div id="<id>"> to the body while
  // measuring, then removes it. Each call needs a unique id or it collides.
  try {
    const { svg } = await mermaid.render(id, source)
    return svg
  } finally {
    // On some error paths Mermaid leaves the measuring node behind; remove it
    // so a streaming session (many render attempts) doesn't accumulate nodes.
    document.getElementById(id)?.remove()
  }
}
