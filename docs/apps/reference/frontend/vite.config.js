// Reference app vite config. `buildfrontend` passes --outDir (the app's derived static dir)
// and --emptyOutDir, so this only needs the vue plugin + the entry.
//
// `npm run build` (the convention) = `vite build`; buildfrontend forwards the outDir.
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  build: {
    sourcemap: true,
    rollupOptions: {
      input: { main: "src/main.ts" },
      output: {
        // Constant names so base.html can reference main.js/main.css with a
        // ?cache_buster=<mtime> cache-buster (no hashed filenames).
        entryFileNames: "main.js",
        assetFileNames: (assetInfo) =>
          assetInfo.name && assetInfo.name.endsWith(".css") ? "main.css" : "[name].[ext]",
      },
    },
  },
})
