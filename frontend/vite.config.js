import { fileURLToPath } from "node:url"
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

// Chunking: @panzoom ships as its own lazy chunk; vendor-shared holds
// packages both the entry and lazy features need. The ~11MB d2 engine
// never enters the graph — d2.ts loads it by URL from a verbatim asset.
const PANZOOM_BUNDLE = /node_modules[\\/]@panzoom[\\/]/
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
            { name: "panzoom", test: PANZOOM_BUNDLE, priority: 1 },
          ],
        },
      },
    },
  },
})
