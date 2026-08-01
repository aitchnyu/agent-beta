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

createInertiaApp({
  title: (title) => `Instant - ${title}`,
  resolve: (name) => {
    const pages = import.meta.glob(["./pages/**/*.vue"], { eager: true })
    const key = `./pages/${name}.vue`
    const page = pages[key]
    if (!page) {
      throw new Error(
        `Inertia page not found: ${key} — rebuild the frontend (npm run build)`,
      )
    }
    return page as DefineComponent
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
