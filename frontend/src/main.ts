import { createApp, h } from "vue"
import type { App as VueApp, DefineComponent } from "vue"
import { HttpResponseError } from "@inertiajs/core"
import { createInertiaApp, router } from "@inertiajs/vue3"
import Layout from "./components/Layout.vue"
import {
  reportErrorEvent,
  reportRejection,
  reportVueError,
} from "./utils/clientError"
import { showErrorToast } from "./utils/sweetalert"
import "./main.scss"
import "vue-multiselect/dist/vue-multiselect.css"
// Eager styles for the lazy JS chunks, otherwise these pages flash of unstyled content.
import "quill/dist/quill.snow.css"
import "highlight.js/styles/github.css"

// Re-entrancy latch for the error pipeline: reporting and toasting are
// themselves fallible (the toast chunk is a network fetch), so without this
// guard a pipeline failure becomes an unhandled rejection → error → …
// infinite loop. Cleared when the in-flight pipeline settles; errors raised
// while busy are dropped, a pipeline's own failure is logged only.
let errorPipelineBusy = false
async function runErrorPipeline(
  run: () => Promise<void> | void,
): Promise<void> {
  if (errorPipelineBusy) return
  errorPipelineBusy = true
  try {
    await run()
  } catch (pipelineErr: unknown) {
    console.error(
      "error pipeline itself failed:",
      pipelineErr instanceof Error ? pipelineErr.stack : pipelineErr,
    )
  } finally {
    errorPipelineBusy = false
  }
}

// Global safety net: surface errors that escape component try/catch as toasts,
// AND ship them to the backend (POST /client-errors) with the source location,
// page url and reporter identity. Vue-caught errors go to app.config.errorHandler
// (below) and do NOT reach here, so there is no double-report.
window.addEventListener("error", (event: ErrorEvent) => {
  const err = event.error
  // Log the stack explicitly as text — passing the object arg renders it only
  // in the dev console (Playwright captures object args as "JSHandle@object").
  console.error("window error:", err?.stack ?? err ?? event.message)
  // reportErrorEvent returns false for resource-load failures (broken
  // <img>/<script>) — those aren't JS errors, so skip the user-facing toast too.
  runErrorPipeline(() => {
    if (!reportErrorEvent(event)) return
    return showErrorToast(err ?? event.message, "Something went wrong")
  })
})
window.addEventListener(
  "unhandledrejection",
  (event: PromiseRejectionEvent) => {
    const reason = event.reason
    console.error(
      "unhandled rejection:",
      reason?.stack ?? reason?.message ?? reason,
    )
    runErrorPipeline(() => {
      reportRejection(event)
      return showErrorToast(reason, "Something went wrong")
    })
  },
)

// Framework pages bundle from ./pages/; the user app's pages bundle from
// ./ours/pages/ (Inertia component name "ours/<Name>"). Both eager into main.js
// (one entry, no per-page chunks).
const pages = import.meta.glob(["./pages/**/*.vue", "./ours/pages/**/*.vue"], {
  eager: true,
}) as Record<string, { default: DefineComponent }>

createInertiaApp({
  // Required, not cosmetic: v3's built-in HTTP client defaults to Laravel's
  // XSRF-TOKEN cookie / X-XSRF-TOKEN header; Django expects csrftoken /
  // X-CSRFToken (set by InertiaMiddleware on every response). With the
  // defaults, every mutating visit fails Django's CSRF check (403).
  http: {
    xsrfCookieName: "csrftoken",
    xsrfHeaderName: "X-CSRFToken",
  },
  title: (title) => `Instant - ${title}`,
  // Default layout: every page renders inside Layout.vue (navbar + slot); reads shared props via usePage()
  layout: () => Layout,
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
    app.config.errorHandler = (err, _instance, info) => {
      console.error("Vue error:", err instanceof Error ? err.stack : err)
      runErrorPipeline(() => {
        reportVueError(err, info)
        return showErrorToast(err, "Something went wrong")
      })
    }
    // Inertia v3 visit failures as toasts, closing the gap in the app's
    // "every error toasts" contract (the handlers above only catch JS/Vue
    // errors, not failed page visits). httpException: preventDefault keeps
    // the user on the current page (Inertia would otherwise swap to an
    // error page) and the toast carries the response's detail; networkError
    // means the server was unreachable mid-visit.
    router.on("httpException", (event) => {
      event.preventDefault()
      const { status, data } = event.detail.response
      showErrorToast(
        new HttpResponseError(`Request failed with status ${status}`, {
          status,
          // Already-parsed object bodies (HttpExceptionResponse) re-serialize
          // so the toast's JSON-detail extraction sees a string either way.
          data: typeof data === "string" ? data : JSON.stringify(data),
          headers: {},
        }),
        "Request failed",
      )
    })
    router.on("networkError", (event) => {
      event.preventDefault()
      showErrorToast(event.detail.error, "Could not reach the server")
    })
    app.use(plugin).mount(el)
  },
})
