// Inertia-demo entry. Minimal createInertiaApp resolving ./pages; axios CSRF
// configured for the GET the page fires. Pages map by component name
// ("DemoPage" -> ./pages/DemoPage.vue).
import { createApp, h } from "vue"
import type { App as VueApp, DefineComponent } from "vue"
import { createInertiaApp } from "@inertiajs/vue3"
import axios from "axios"

document.addEventListener("DOMContentLoaded", () => {
  axios.defaults.xsrfCookieName = "csrftoken"
  axios.defaults.xsrfHeaderName = "X-CSRFTOKEN"
})

createInertiaApp({
  title: (title) => `Demo - ${title}`,
  resolve: (name) => {
    const pages = import.meta.glob(["./pages/**/*.vue"], { eager: true })
    return pages[`./pages/${name}.vue`] as DefineComponent
  },
  setup({ el, App, props, plugin }) {
    const app: VueApp = createApp({ render: () => h(App, props) })
    app.use(plugin).mount(el)
  },
})
