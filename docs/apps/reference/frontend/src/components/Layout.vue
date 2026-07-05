<script setup lang="ts">
// Shared shell every app page wraps itself in. The signed-in viewer is an
// Inertia shared prop (the host's SharedPropsMiddleware injects it on every
// page), so it isn't threaded per-view. A "Home" link returns to the host app.
import { computed } from "vue"
import { usePage } from "@inertiajs/vue3"

const page = usePage()
// `user` (UserProfile: public_id + title) is shared, not under the page's own props.
const user = computed(() => (page.props as { user?: { title: string } }).user)
</script>

<template>
  <div>
    <nav class="navbar navbar-light bg-light ref-nav">
      <a class="btn btn-outline-secondary btn-sm ref-home" href="/">Home</a>
      <span v-if="user" class="navbar-text ref-user">Hello, {{ user.title }}!</span>
    </nav>
    <main class="container py-3">
      <slot />
    </main>
  </div>
</template>
