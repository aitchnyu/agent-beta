// Reference app entry. Mirrors the host main.ts: createInertiaApp, axios CSRF,
// a global error → toast safety net, and Bootstrap. Apps adopt this shell.
//
// Pages resolve from ./pages (each app's own bundle), so an app's component
// name (e.g. "ReferencePage") maps to ./pages/ReferencePage.vue here.
import { createApp, h } from "vue"
import type { App as VueApp, DefineComponent } from "vue"
import { createInertiaApp } from "@inertiajs/vue3"
import axios from "axios"
import "bootstrap"
import { showErrorToast } from "./utils/showErrorToast"

// CSRF for axios (every call must still be try/catch + toast in the caller).
document.addEventListener("DOMContentLoaded", () => {
  axios.defaults.xsrfCookieName = "csrftoken"
  axios.defaults.xsrfHeaderName = "X-CSRFTOKEN"
})

// Global safety net: surface errors that escape a component's try/catch.
// Do NOT throw after toasting — the global handler would double-toast.
window.addEventListener("error", (event: ErrorEvent) => {
  console.error("window error:", event.error ?? event.message)
  showErrorToast(event.error ?? event.message, "Something went wrong")
})
window.addEventListener("unhandledrejection", (event: PromiseRejectionEvent) => {
  console.error("unhandled rejection:", event.reason)
  showErrorToast(event.reason, "Something went wrong")
})

createInertiaApp({
  title: (title) => `App - ${title}`,
  resolve: (name) => {
    const pages = import.meta.glob(["./pages/**/*.vue"], { eager: true })
    return pages[`./pages/${name}.vue`] as DefineComponent
  },
  setup({ el, App, props, plugin }) {
    const app: VueApp = createApp({ render: () => h(App, props) })
    app.config.errorHandler = (err) => {
      console.error("Vue error:", err)
      showErrorToast(err, "Something went wrong")
    }
    app.use(plugin).mount(el)
  },
})
