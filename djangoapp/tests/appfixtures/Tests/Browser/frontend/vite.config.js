// Browser fixture frontend. `buildapp` passes --outDir (the app's derived static
// dir) + --emptyOutDir, so this only needs the vue plugin + the entry. Output
// names are constant (main.js/main.css) so base.html can reference them with a
// ?cache_buster=<mtime> cache-buster.
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  build: {
    sourcemap: true,
    rollupOptions: {
      input: { main: "src/main.ts" },
      output: {
        entryFileNames: "main.js",
        assetFileNames: (assetInfo) =>
          assetInfo.name && assetInfo.name.endsWith(".css") ? "main.css" : "[name].[ext]",
      },
    },
  },
})
