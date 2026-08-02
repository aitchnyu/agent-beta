import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  // Assets/chunks (incl. dynamic-import chunks) resolve under the host static
  // URL /static/djangoapp/, where Django serves them (see base.html).
  base: "/static/djangoapp/",
  build: {
    outDir: "../djangoapp/static/djangoapp",
    sourcemap: true,
    emptyOutDir: true, // outDir lives outside the frontend root, tell Vite toclean up old artifacts
    rollupOptions: {
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
