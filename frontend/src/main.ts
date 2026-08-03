import { createApp, h } from "vue"
import type { App as VueApp, DefineComponent } from "vue"
import { createInertiaApp } from "@inertiajs/vue3"
import axios from "axios"
import { showErrorToast } from "./utils/sweetalert"
import "./main.scss"
import "vue-multiselect/dist/vue-multiselect.css"
// Eager styles for the lazy JS chunks, otherwise these pages flash of unstyled content.
import "quill/dist/quill.snow.css"
import "highlight.js/styles/github.css"

// Configure axios CSRF token when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  axios.defaults.xsrfCookieName = "csrftoken"
  axios.defaults.xsrfHeaderName = "X-CSRFTOKEN"
})

// Global safety net: surface errors that escape component try/catch as toasts,
// and log the full error so the stack/Zod issues are visible in the console.
// Vue-caught errors go to app.config.errorHandler (below) and do NOT reach here,
// so there is no double-toast.
window.addEventListener("error", (event: ErrorEvent) => {
  const err = event.error
  // Log the stack explicitly as text — passing the object arg renders it only
  // in the dev console (Playwright captures object args as "JSHandle@object").
  console.error("window error:", err?.stack ?? err ?? event.message)
  showErrorToast(err ?? event.message, "Something went wrong")
})
window.addEventListener(
  "unhandledrejection",
  (event: PromiseRejectionEvent) => {
    const reason = event.reason
    console.error(
      "unhandled rejection:",
      reason?.stack ?? reason?.message ?? reason,
    )
    showErrorToast(reason, "Something went wrong")
  },
)

// Framework pages bundle from ./pages/; the user app's pages bundle from
// ./ours/pages/ (Inertia component name "ours/<Name>"). Both eager into main.js
// (one entry, no per-page chunks). Pages must NOT do a cold dynamic import()
// in onMounted — that makes Inertia v2 silently roll the navigation back. The
// heavy page deps (hljs/marked via filePreview, quill via RichTextEditor) are
// separate lazy chunks, pre-warmed into the cache here at boot so a later swap
// resolves them from cache (a cache-hit import has no async gap, so no rollback).
const pages = import.meta.glob(["./pages/**/*.vue", "./ours/pages/**/*.vue"], {
  eager: true,
}) as Record<string, { default: DefineComponent }>

// TODO this could be simpler when we do Inertia v3.
// Pull the heavy (render-critical) lazy chunks into the module cache after boot.
// The user has already loaded the app shell (a hard load, not a swap), so these
// imports are swap-safe; once cached, onMounted/async-component imports during a
// later swap resolve instantly. Deferred to idle to avoid competing with first
// paint. Both are fire-and-forget.
const preloadHeavyChunks = () => {
  void import("./utils/filePreview")
  void import("./components/RichTextEditor.vue")
}
function schedulePreload() {
  if (typeof window.requestIdleCallback === "function") {
    window.requestIdleCallback(preloadHeavyChunks)
  } else {
    setTimeout(preloadHeavyChunks, 1000)
  }
}

createInertiaApp({
  title: (title) => `Instant - ${title}`,
  resolve: (name) => {
    // "ours/<Name>" → ./ours/pages/<Name>.vue; everything else → ./pages/<name>.vue
    const key = name.startsWith("ours/")
      ? `./ours/pages/${name.slice("ours/".length)}.vue`
      : `./pages/${name}.vue`
    const mod = pages[key]
    if (!mod) {
      throw new Error(
        `Inertia page not found: ${key} — rebuild the frontend (npm run build)`,
      )
    }
    return mod.default
  },
  setup({ el, App, props, plugin }) {
    const app: VueApp = createApp({ render: () => h(App, props) })
    app.config.errorHandler = (err) => {
      console.error("Vue error:", err instanceof Error ? err.stack : err)
      showErrorToast(err, "Something went wrong")
    }
    app.use(plugin).mount(el)
    schedulePreload()
  },
})
