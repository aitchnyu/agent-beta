import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

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
      },
    },
  },
})
