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

// Global safety net: surface errors that escape component try/catch as toasts.
// Vue-caught errors go to app.config.errorHandler (below) and do NOT reach here,
// so there is no double-toast.
window.addEventListener("error", (event: ErrorEvent) => {
  showErrorToast(event.error ?? event.message, "Something went wrong")
})
window.addEventListener(
  "unhandledrejection",
  (event: PromiseRejectionEvent) => {
    showErrorToast(event.reason, "Something went wrong")
  },
)

createInertiaApp({
  title: (title) => `Instant - ${title}`,
  resolve: (name) => {
    const pages = import.meta.glob(["./pages/**/*.vue"], { eager: true })
    return pages[`./pages/${name}.vue`] as DefineComponent
  },
  setup({ el, App, props, plugin }) {
    const app: VueApp = createApp({ render: () => h(App, props) })
    app.config.errorHandler = (err) => {
      showErrorToast(err, "Something went wrong")
    }
    app.use(plugin).mount(el)
  },
})
