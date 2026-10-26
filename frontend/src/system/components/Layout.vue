<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import { Link, usePage } from "@inertiajs/vue3"
import { SharedPropsSchema } from "../schemas/sharedProps"
import CollapsibleButton from "./CollapsibleButton.vue"
import HideOnScroll from "./HideOnScroll.vue"
import UserMenu from "./UserMenu.vue"
import LucideIcon from "./LucideIcon.vue"
import leafIcon from "../icons/leaf.svg"
import logInIcon from "../icons/log-in.svg"
import { fileUrl } from "../pages/files/files"

// The signed-in viewer's profile + superuser flag are Inertia shared props,
// injected for every page by SharedPropsMiddleware (not threaded per-view).
const page = usePage()
const shared = computed(() => SharedPropsSchema.parse(page.props))
const user = computed(() => shared.value.user)
const isSuperuser = computed(() => shared.value.viewer_is_superuser)
const loginProviders = computed(() => shared.value.login_providers)

// The superuser nav links, rendered flat on wide viewports and inside the
// "Menu" dropdown on narrow ones (one source of truth for both shapes). An
// entry with children (Code) renders as its own dropdown in both shapes.
const codeLinks = [
  { href: "/git/uncommitted/", label: "Uncommitted" },
  { href: "/git/commits", label: "Commits" },
  { href: fileUrl("main/ourapp"), label: "Files" },
]
type NavEntry = { href: string; label: string; children?: typeof codeLinks }
const navLinks = computed<NavEntry[]>(() =>
  isSuperuser.value
    ? [
        { href: "/manage/models", label: "Models" },
        { href: "/git/uncommitted/", label: "Code", children: codeLinks },
        { href: "/users/list", label: "Users" },
      ]
    : [],
)

// Responsive collapse: below the breakpoint the links fold into a native
// <details> dropdown (same pattern as Sign in / the user menu). Home and
// the user badge stay outside it — identity and notifications must remain
// one click away at every width. The query is evaluated at setup (not on
// mount) so narrow devices never render one wide-layout frame first.
const navMedia = window.matchMedia("(max-width: 767.98px)")
const navCompact = ref(navMedia.matches)
function onMediaChange(event: MediaQueryListEvent): void {
  navCompact.value = event.matches
}
onMounted(() => navMedia.addEventListener("change", onMediaChange))
onBeforeUnmount(() => navMedia.removeEventListener("change", onMediaChange))

// Native <details> dropdowns Layout owns directly (Sign in, the compact
// Menu): close on outside click and Escape — links inside navigate away,
// closing them. The Code dropdown is a CollapsibleButton that manages its
// own closing.
const signin = ref<HTMLDetailsElement>()
const navMenu = ref<HTMLDetailsElement>()
function closeMenus(): void {
  for (const el of [signin.value, navMenu.value]) {
    if (el) el.open = false
  }
}
function onDocClick(e: MouseEvent) {
  for (const el of [signin.value, navMenu.value]) {
    if (el?.open && !el.contains(e.target as Node)) el.open = false
  }
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") closeMenus()
}
onMounted(() => {
  document.addEventListener("click", onDocClick)
  document.addEventListener("keydown", onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick)
  document.removeEventListener("keydown", onKeydown)
})
</script>

<template>
  <div>
    <HideOnScroll class="layout-navbar">
      <Link class="nav-link" href="/" aria-label="Home"
        ><img :src="leafIcon" alt="" class="home-leaf-icon" />
      </Link>
      <template v-if="!navCompact">
        <template v-for="link in navLinks" :key="link.href">
          <CollapsibleButton
            v-if="link.children"
            class="layout-navmenu"
            :label="link.label"
            :links="link.children"
            summary-class="nav-link layout-menu-summary layout-navmenu-summary"
            panel-class="layout-menu-panel layout-navmenu-list"
            link-class="layout-menu-link layout-navmenu-link"
          />
          <Link v-else class="nav-link" :href="link.href">{{
            link.label
          }}</Link>
        </template>
      </template>
      <details v-else-if="navLinks.length" ref="navMenu" class="layout-navmenu">
        <summary class="nav-link layout-menu-summary layout-navmenu-summary">
          Menu
        </summary>
        <div class="layout-menu-panel layout-navmenu-list">
          <template v-for="link in navLinks" :key="link.href">
            <CollapsibleButton
              v-if="link.children"
              class="layout-navmenu"
              :label="link.label"
              :links="link.children"
              summary-class="layout-menu-link layout-navmenu-link"
              panel-class="layout-menu-panel layout-navmenu-list"
              link-class="layout-menu-link layout-navmenu-link"
              @linkclick="closeMenus"
            />
            <Link
              v-else
              class="layout-menu-link layout-navmenu-link"
              :href="link.href"
              @click="closeMenus"
              >{{ link.label }}</Link
            >
          </template>
        </div>
      </details>
      <template v-if="user">
        <UserMenu class="ms-auto" :user="user" />
      </template>
      <details
        v-else-if="loginProviders?.length"
        ref="signin"
        class="layout-signin ms-auto"
      >
        <summary class="btn btn-sm btn-outline-primary layout-menu-summary">
          <LucideIcon :src="logInIcon" /> Sign in
        </summary>
        <div class="layout-menu-panel layout-signin-menu">
          <a
            v-for="p in loginProviders"
            :key="p.id"
            class="layout-menu-link layout-signin-link"
            :href="p.url"
            >{{ p.name }}</a
          >
        </div>
      </details>
      <button
        v-else
        class="btn btn-sm btn-outline-primary ms-auto"
        disabled
        title="No login methods are configured on this deployment"
      >
        <LucideIcon :src="logInIcon" /> Sign in
      </button>
    </HideOnScroll>
    <slot />
  </div>
</template>
