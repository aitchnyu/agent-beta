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
    rollupOptions: {
      input: {
        main: "src/main.ts",
      },
      output: {
        entryFileNames: "main.js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith(".css")) {
            return "main.css"
          }
          return "[name].[ext]"
        },
      },
    },
  },
})
