import { createApp, h } from "vue"
import type { App as VueApp, DefineComponent } from "vue"
import { createInertiaApp } from "@inertiajs/vue3"
import axios from "axios"
import { showErrorToast } from "./utils/sweetalert"
import "./main.scss"
import "bootstrap"
import "vue-multiselect/dist/vue-multiselect.css"
import "quill/dist/quill.snow.css"

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

// All pages bundle eagerly into main.js (one entry, no per-page chunks). Pages
// must NOT do a dynamic import() in onMounted — that makes Inertia v2 silently
// roll the navigation back. (Heavy page deps, e.g. GitDiff's highlight.js, are
// imported at module load and ship in main.js.)
const pages = import.meta.glob(["./pages/**/*.vue"], {
  eager: true,
}) as Record<string, { default: DefineComponent }>

createInertiaApp({
  title: (title) => `Instant - ${title}`,
  resolve: (name) => {
    const key = `./pages/${name}.vue`
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
  },
})
