import fs from "node:fs"
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

// Split Mermaid into two lazy chunks
// mermaid-core — the entry + shared internals + ER/state diagrams + dagre/d3 layout engine
// mermaid-uncommon  — every other diagram type + cytoscape/katex/roughjs...
// Tests match by module path; priority resolves overlaps (core > uncommon).
function mermaidDeps() {
  const pkgJson = (name) => {
    try {
      return JSON.parse(
        fs.readFileSync(`node_modules/${name}/package.json`, "utf8"),
      )
    } catch {
      return null
    }
  }
  const seen = new Set()
  const out = new Set()
  const stack = ["mermaid"]
  while (stack.length) {
    const name = stack.pop()
    if (seen.has(name)) continue
    seen.add(name)
    const pj = pkgJson(name)
    if (!pj) continue
    out.add(name)
    for (const dep of Object.keys(pj.dependencies ?? {})) stack.push(dep)
  }
  // Shared with the app — keep out of the mermaid chunks.
  out.delete("marked")
  out.delete("dompurify")
  return out
}
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
const mermaidRelated = new RegExp(
  `node_modules[\\\\/](${[...mermaidDeps()].map(esc).join("|")})([\\\\/]|$)`,
)
const baseName = (id) => {
  const parts = id.split(/[\\/]/)
  return parts[parts.length - 1]
}
// Core: the dagre/d3 layout engine, plus the mermaid package's internals and the
// ER/state diagram modules (the only diagrams this app uses). Rare diagram
// modules (pie/sequence/gantt/…) are mermaid/dist files whose name carries
// "Diagram" and aren't ER/state, so they fall through to uncommon.
const isCore = (id) => {
  if (/node_modules[\\/](dagre-d3-es|d3|d3-[a-z-]+)[\\/]/.test(id)) return true
  if (!/node_modules[\\/]mermaid[\\/]dist[\\/]/.test(id)) return false
  const name = baseName(id)
  return !/Diagram-/.test(name) || /^erDiagram-|^stateDiagram(-v2)?-/.test(name)
}

export default defineConfig({
  plugins: [vue()],
  // Assets/chunks (incl. dynamic-import chunks) resolve under the host static
  // URL /static/djangoapp/, where Django serves them (see base.html).
  base: "/static/djangoapp/",
  // Bootstrap's SCSS is @import-based; the selective build in styles/_bootstrap
  // uses @import to match, so silence that deprecation (not the app's own @use).
  css: {
    preprocessorOptions: {
      // Bootstrap's SCSS is @import-based and uses legacy Sass (if()/global
      // built-ins/color funcs) — silence its dep warnings (quietDeps covers
      // node_modules; "import" covers our @use of the @import-based build).
      scss: { quietDeps: true, silenceDeprecations: ["import"] },
    },
  },
  build: {
    outDir: "../djangoapp/static/djangoapp",
    sourcemap: true,
    emptyOutDir: true, // outDir lives outside the frontend root, tell Vite toclean up old artifacts
    rolldownOptions: {
      input: {
        main: "src/main.ts",
      },
      output: {
        entryFileNames: "main.js",
        // Pin the entry CSS to "main.css" (base.html references it by that
        // name). CSS emitted by async chunks keeps its own name instead of all
        // collapsing to "main.css" and colliding into "main2.css".
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith(".css")) {
            return assetInfo.name === "main.css"
              ? "main.css"
              : "assets/[name][extname]"
          }
          return "[name].[ext]"
        },
        // Two Mermaid chunks: core (entry+shared+ER/state+dagre/d3) loads on
        // first diagram render; uncommon (rare diagrams+cytoscape/katex/roughjs)
        // loads only if a rare type renders (never, for us). See helpers above.
        codeSplitting: {
          groups: [
            { name: "mermaid-core", test: isCore, priority: 2 },
            { name: "mermaid-uncommon", test: mermaidRelated, priority: 1 },
          ],
        },
      },
    },
  },
})
