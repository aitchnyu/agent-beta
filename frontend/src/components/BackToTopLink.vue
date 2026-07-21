<script setup lang="ts">
import { Link } from "@inertiajs/vue3"

// "Back to top" = up one level in the app/table route hierarchy
// (e.g. /manage/apps/<app> -> /manage/apps). A real Inertia <Link>, so it
// navigates rather than scrolling, and stays keyboard-accessible.
defineProps<{ href: string }>()
</script>

<template>
  <Link class="apps-back-to-top" :href="href">
    <span class="apps-back-to-top-arrow" aria-hidden="true">↑</span>
    <slot />
  </Link>
</template>
