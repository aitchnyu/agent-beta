<script setup lang="ts">
import { inject, ref } from "vue"
import type { Ref } from "vue"
import { Link } from "@inertiajs/vue3"
import { navbarCloseMenuKey, navbarCompactKey } from "./navbar"

// A top-level navbar entry: a flat nav link on wide viewports, a Menu
// entry that collapses the compact Menu on navigate. Defaults to the wide
// shape when rendered outside a Navbar.
defineProps<{ href: string }>()
const compact = inject<Ref<boolean>>(navbarCompactKey, ref(false))
const closeMenu = inject<() => void>(navbarCloseMenuKey, () => {})
</script>

<template>
  <Link
    :class="compact ? 'layout-menu-link layout-navmenu-link' : 'nav-link'"
    :href="href"
    @click="closeMenu"
    ><slot
  /></Link>
</template>
