<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
</script>

<template>
  <nav class="nav gap-2 mb-3" aria-label="Git views">
    <Link class="nav-link" href="/git/uncommitted/">Uncommitted</Link>
    <Link class="nav-link" href="/git/commits">Commits</Link>
  </nav>
</template>
