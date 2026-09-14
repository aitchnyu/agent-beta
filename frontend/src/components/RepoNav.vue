<script setup lang="ts">
import { Link, usePage } from "@inertiajs/vue3"
import { fileUrl } from "../utils/files"

// The one sub-nav shared by every Code page (git + files viewers). The active
// tab derives from the current URL, so client-side Inertia swaps keep it right.
const page = usePage()
const sections = [
  {
    label: "Uncommitted",
    href: "/git/uncommitted/",
    match: "/git/uncommitted",
  },
  { label: "Commits", href: "/git/commits", match: "/git/commits" },
  { label: "Files", href: fileUrl("main/ourapp"), match: "/files" },
]
const active = (match: string): boolean => page.url.startsWith(match)
</script>

<template>
  <nav class="nav repo-nav gap-2 mb-3" aria-label="Code views">
    <Link
      v-for="s in sections"
      :key="s.label"
      class="nav-link"
      :class="{ active: active(s.match) }"
      :aria-current="active(s.match) ? 'page' : undefined"
      :href="s.href"
      >{{ s.label }}</Link
    >
  </nav>
</template>
