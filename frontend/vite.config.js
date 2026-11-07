import { fileURLToPath } from "node:url"
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

// Chunking (pinned by test_files.py: a page without diagrams requests no
// d2-* chunk): @d2lang/d2 + @panzoom ship as ONE lazy chunk — components/d2.ts's
// `import("@d2lang/d2")` is the boundary — and vendor-shared holds packages
// both the entry and d2 need (the pressure valve keeping main.js from
// gaining a static import edge into the ~11.5 MB d2 bundle, the regression
// that keeps returning).
const D2_BUNDLE = /node_modules[\\/](@d2lang|@panzoom)[\\/]/
const VENDOR_SHARED =
  /node_modules[\\/](dompurify|lodash-es|lodash\.isequal|dayjs|es-toolkit|khroma|stylis|ts-dedent|uuid)[\\/]|vite[/\\]preload-helper/

export default defineConfig({
  plugins: [vue()],
  // `@` → src/: generated sdks import http.ts depth-independently.
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
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
