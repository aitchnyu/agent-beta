import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

// One lazy d2 bundle + one small eager shared chunk:
//   d2 — @d2lang/d2 (WASM renderer, web worker, fonts) + @panzoom in a
//     SINGLE chunk that loads on the first diagram render; utils/d2.ts's
//     `import("@d2lang/d2")` is the lazy boundary.
//   vendor-shared — packages and bundler helpers that BOTH the entry and
//     d2 need (dompurify, lodash-*, dayjs, es-toolkit, khroma, …, plus
//     vite's preload helper). Rolldown assigns a module to exactly one
//     chunk, and whenever a module the entry needs is captured by (or parked
//     inside) the d2 chunk, main.js gains a STATIC import edge into the
//     whole ~11.5 MB bundle — the regression that keeps returning. This group
//     is the pressure valve: those modules live in a small chunk the entry
//     imports directly, and d2 imports it lazily like everyone else.
// test_files.py pins the outcome: a page without diagrams requests no
// d2-* chunk at all.
const D2_BUNDLE = /node_modules[\\/](@d2lang|@panzoom)[\\/]/
const VENDOR_SHARED =
  /node_modules[\\/](dompurify|lodash-es|lodash\.isequal|dayjs|es-toolkit|khroma|stylis|ts-dedent|uuid)[\\/]|vite[/\\]preload-helper/

export default defineConfig({
  plugins: [vue()],
  // Assets/chunks (incl. dynamic-import chunks) resolve under the host static
  // URL /static/djangoapp/, where Django serves them (see base.html).
  base: "/static/djangoapp/",
  // Bootstrap's SCSS is @import-based; the selective build in
  // system/styles/_bootstrap uses @import to match, so silence that
  // deprecation (not the app's own @use).
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
            { name: "d2", test: D2_BUNDLE, priority: 1 },
          ],
        },
      },
    },
  },
})
