<script setup lang="ts">
import { computed } from "vue"
import { usePage } from "@inertiajs/vue3"
import { SharedPropsSchema } from "../schemas/sharedProps"
import CollapsibleButton from "./CollapsibleButton.vue"
import LucideIcon from "./LucideIcon.vue"
import Navbar from "./navbar/Navbar.vue"
import NavbarItem from "./navbar/NavbarItem.vue"
import NavbarMenu from "./navbar/NavbarMenu.vue"
import NavbarMenuItem from "./navbar/NavbarMenuItem.vue"
import UserMenu from "./UserMenu.vue"
import logInIcon from "../icons/log-in.svg"
import { fileUrl } from "../pages/files/files"

// Shared props arrive via SharedPropsMiddleware (not per-view). The navbar
// is declarative — the navbar/ components own the responsive machinery.
const page = usePage()
const shared = computed(() => SharedPropsSchema.parse(page.props))
</script>

<template>
  <div>
    <Navbar>
      <template v-if="shared.viewer_is_superuser">
        <NavbarItem href="/manage/models">Models</NavbarItem>
        <NavbarMenu label="Code">
          <NavbarMenuItem href="/git/uncommitted/">Uncommitted</NavbarMenuItem>
          <NavbarMenuItem href="/git/commits">Commits</NavbarMenuItem>
          <NavbarMenuItem :href="fileUrl('main/ourapp')">Files</NavbarMenuItem>
        </NavbarMenu>
        <NavbarItem href="/users/list">Users</NavbarItem>
      </template>
      <template #right>
        <UserMenu v-if="shared.user" class="ms-auto" :user="shared.user" />
        <CollapsibleButton
          v-else-if="shared.login_providers?.length"
          class="layout-signin ms-auto"
          summary-class="btn btn-sm btn-outline-primary layout-menu-summary"
          panel-class="layout-menu-panel layout-signin-menu"
        >
          <template #summary>
            <LucideIcon :src="logInIcon" /> Sign in
          </template>
          <a
            v-for="p in shared.login_providers"
            :key="p.id"
            class="layout-menu-link layout-signin-link"
            :href="p.url"
            >{{ p.name }}</a
          >
        </CollapsibleButton>
        <button
          v-else
          class="btn btn-sm btn-outline-primary ms-auto"
          disabled
          title="No login methods are configured on this deployment"
        >
          <LucideIcon :src="logInIcon" /> Sign in
        </button>
      </template>
    </Navbar>
    <slot />
  </div>
</template>
