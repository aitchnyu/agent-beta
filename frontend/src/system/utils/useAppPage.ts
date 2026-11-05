import { computed } from "vue"
import { usePage } from "@inertiajs/vue3"
import type { z } from "zod"
import { SharedPropsSchema } from "../schemas/sharedProps"

/**
 * Parse the shared viewer props (`user`, `viewer_is_superuser`, …) —
 * the top level Inertia merges on every page via SharedPropsMiddleware.
 * Computed inside: Inertia swaps the whole page object on every
 * visit/reload, so the parse must live in a computed to stay live.
 * For shared chrome components that read no feature data.
 */
export function useSharedProps() {
  const page = usePage()
  return computed(() => SharedPropsSchema.parse(page.props))
}

/**
 * Parse an Inertia page payload's two levels, reactively.
 *
 * The page's data lives under the inner `props` key (views pass
 * `{"props": …}`); `shared` is useSharedProps above. Inertia swaps the
 * whole page object on every visit/reload — parse inside a computed; a
 * captured `page.props` snapshot goes stale on the next swap.
 *
 * Usage: `const { shared, data: p } = useAppPage(FeaturePropsSchema)`
 * — `p.value.x` in script, `p.x` in template.
 */
export function useAppPage<Schema extends z.ZodType>(featureSchema: Schema) {
  const shared = useSharedProps()
  const data = computed(() =>
    featureSchema.parse(
      (usePage().props as unknown as { props: z.input<Schema> }).props,
    ),
  )
  return { shared, data }
}
