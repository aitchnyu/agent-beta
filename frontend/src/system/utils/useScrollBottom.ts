import { nextTick, type Ref } from "vue"
import { watch } from "vue"

// Keep a scroll container pinned to its bottom as `toWatch` changes (e.g. bash
// output grows, reasoning streams) — by default only when it's already near the
// bottom, so a user who scrolled up to read earlier output isn't yanked back
// down. Pass `always` for a live tail (e.g. streaming reasoning) that should
// follow unconditionally. No-op when the element is gone.
export function useScrollBottom(
  element: Ref<HTMLElement | null>,
  toWatch: () => unknown,
  always = false,
) {
  watch(
    toWatch,
    () => {
      // Measure BEFORE the DOM flush: with flush:"post" the watcher runs after
      // Vue's update, but the scroll position we care about is the one the user
      // is currently on (pre-update). `nearBottom` is true when the viewport is
      // within ~32px of the end — about a thumb's worth of slack — so we only
      // auto-follow when the user is already watching the tail.
      const node = element.value
      const nearBottom =
        always ||
        (!!node && node.scrollHeight - node.scrollTop - node.clientHeight < 32)
      void nextTick(() => {
        if (nearBottom && element.value) {
          element.value.scrollTop = element.value.scrollHeight
        }
      })
    },
    { flush: "post" },
  )
}
