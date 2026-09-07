import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

// One lazy mermaid bundle + one small eager shared chunk:
//   mermaid — mermaid + its exclusive engines (d3/dagre layout, cytoscape,
//     katex, roughjs, …) in a SINGLE chunk that loads on the first diagram
//     render; utils/mermaid.ts's `import("mermaid")` is the lazy boundary.
//   vendor-shared — packages and bundler helpers that BOTH the entry and
//     mermaid need (dompurify, lodash-*, dayjs, es-toolkit, khroma, …, plus
//     vite's preload helper). Rolldown assigns a module to exactly one
//     chunk, and whenever a module the entry needs is captured by (or parked
//     inside) the mermaid chunk, main.js gains a STATIC import edge into the
//     whole 3+ MB bundle — the regression that keeps returning. This group
//     is the pressure valve: those modules live in a small chunk the entry
//     imports directly, and mermaid imports it lazily like everyone else.
// test_files.py pins the outcome: a page without diagrams requests no
// mermaid-* chunk at all.
const MERMAID_BUNDLE =
  /node_modules[\\/](mermaid|@mermaid-js|@braintree|@iconify|@upsetjs|cytoscape|cytoscape-[a-z-]+|cose-base|layout-base|dagre-d3-es|d3|d3-[a-z-]+|internmap|katex|roughjs)[\\/]/
const VENDOR_SHARED =
  /node_modules[\\/](dompurify|lodash-es|lodash\.isequal|dayjs|es-toolkit|khroma|stylis|ts-dedent|uuid)[\\/]|vite[/\\]preload-helper/

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
    emptyOutDir: true, // outDir lives outside the frontend root, tell Vite to clean up old artifacts
    // Emit .vite/manifest.json mapping logical entry names to the hashed
    // output files; djangoapp.templatetags.app_static reads it to resolve
    // main.js/main.css in templates.
    manifest: true,
    rolldownOptions: {
      input: {
        main: "src/main.ts",
      },
      output: {
        // Hashed entry: self-busts the cache, and a stable module URL is
        // correctness — lazy chunks import back into the entry, and a
        // query-string buster instead would execute main.js twice (second
        // createInertiaApp boot rolls swaps back). Templates resolve both
        // entry files via .vite/manifest.json (hashed_entry filter).
        entryFileNames: "main-[hash].js",
        codeSplitting: {
          groups: [
            { name: "vendor-shared", test: VENDOR_SHARED, priority: 2 },
            { name: "mermaid", test: MERMAID_BUNDLE, priority: 1 },
          ],
        },
      },
    },
  },
})
