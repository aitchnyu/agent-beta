<script setup lang="ts">
import { Link } from "@inertiajs/vue3"

// "Back to top" = up one level in the collection/app/table route hierarchy
// (e.g. /apps/a/<coll>/list -> /apps/collections). A real Inertia <Link>, so it
// navigates rather than scrolling, and stays keyboard-accessible.
defineProps<{ href: string }>()
</script>

<template>
  <Link class="apps-back-to-top" :href="href">
    <span class="apps-back-to-top-arrow" aria-hidden="true">↑</span>
    <slot />
  </Link>
</template>
