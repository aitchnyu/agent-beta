<script setup lang="ts">
import { Link } from "@inertiajs/vue3"

// One link inside a NavbarMenu panel — placement-agnostic (the panel is
// the same dropdown in both navbar shapes).
defineProps<{ href: string }>()
</script>

<template>
  <Link class="layout-menu-link layout-navmenu-link" :href="href"
    ><slot
  /></Link>
</template>
