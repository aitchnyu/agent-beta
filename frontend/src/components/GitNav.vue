<script setup lang="ts">
import { Link } from "@inertiajs/vue3"
</script>

<template>
  <nav class="d-flex gap-2 mb-3" aria-label="Git views">
    <Link class="btn btn-outline-secondary btn-sm" href="/git"
      >Uncommitted</Link
    >
    <Link class="btn btn-outline-secondary btn-sm" href="/git/commits"
      >Commits</Link
    >
  </nav>
</template>
