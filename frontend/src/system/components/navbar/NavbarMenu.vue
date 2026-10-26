<script setup lang="ts">
import { inject, ref } from "vue"
import type { Ref } from "vue"
import CollapsibleButton from "../CollapsibleButton.vue"
import { navbarCloseMenuKey, navbarCompactKey } from "./navbar"

// A top-level dropdown: CollapsibleButton with the navbar's placement
// classes; the slot holds NavbarMenuItem entries. Defaults to the wide
// shape when rendered outside a Navbar.
defineProps<{ label: string }>()
const compact = inject<Ref<boolean>>(navbarCompactKey, ref(false))
const closeMenu = inject<() => void>(navbarCloseMenuKey, () => {})
</script>

<template>
  <CollapsibleButton
    class="layout-navmenu"
    :label="label"
    :summary-class="
      compact
        ? 'layout-menu-link layout-navmenu-link'
        : 'nav-link layout-menu-summary layout-navmenu-summary'
    "
    panel-class="layout-menu-panel layout-navmenu-list"
    @linkclick="closeMenu"
  >
    <slot />
  </CollapsibleButton>
</template>
