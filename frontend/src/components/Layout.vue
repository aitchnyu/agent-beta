<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import { Link, usePage } from "@inertiajs/vue3"
import { SharedPropsSchema } from "../schemas"
import HideOnScroll from "./HideOnScroll.vue"
import UserMenu from "./UserMenu.vue"

// The signed-in viewer's profile + superuser flag are Inertia shared props,
// injected for every page by SharedPropsMiddleware (not threaded per-view).
const page = usePage()
const shared = computed(() => SharedPropsSchema.parse(page.props))
const user = computed(() => shared.value.user)
const isSuperuser = computed(() => shared.value.viewer_is_superuser)
const loginProviders = computed(() => shared.value.login_providers)

// The superuser nav links, rendered flat on wide viewports and inside the
// "Menu" dropdown on narrow ones (one source of truth for both shapes).
const navLinks = computed(() =>
  isSuperuser.value
    ? [
        { href: "/manage/models", label: "Models" },
        { href: "/git/uncommitted/", label: "Code" },
        { href: "/users/list", label: "Users" },
      ]
    : [],
)

// Responsive collapse: below the breakpoint the links fold into a native
// <details> dropdown (same pattern as Sign in / the user menu). Home and
// the user badge stay outside it — identity and notifications must remain
// one click away at every width.
const navCompact = ref(false)
let navMedia: MediaQueryList | null = null
function onMediaChange(event: MediaQueryListEvent): void {
  navCompact.value = event.matches
}
onMounted(() => {
  navMedia = window.matchMedia("(max-width: 767px)")
  navCompact.value = navMedia.matches
  navMedia.addEventListener("change", onMediaChange)
})
onBeforeUnmount(() => navMedia?.removeEventListener("change", onMediaChange))

// Native <details> dropdowns (Sign in, the compact nav Menu): close on any
// outside click — they would otherwise stay open; links inside navigate
// away, closing them. UserMenu carries the same handling for its own
// dropdown.
const signin = ref<HTMLDetailsElement>()
const navMenu = ref<HTMLDetailsElement>()
function onDocClick(e: MouseEvent) {
  for (const el of [signin.value, navMenu.value]) {
    if (el?.open && !el.contains(e.target as Node)) el.open = false
  }
}
onMounted(() => document.addEventListener("click", onDocClick))
onBeforeUnmount(() => document.removeEventListener("click", onDocClick))
</script>

<template>
  <div>
    <HideOnScroll class="layout-navbar">
      <Link class="nav-link" href="/">Home</Link>
      <template v-if="!navCompact">
        <Link
          v-for="link in navLinks"
          :key="link.href"
          class="nav-link"
          :href="link.href"
          >{{ link.label }}</Link
        >
      </template>
      <details v-else-if="navLinks.length" ref="navMenu" class="layout-navmenu">
        <summary class="nav-link layout-navmenu-summary">Menu</summary>
        <div class="layout-navmenu-list">
          <Link
            v-for="link in navLinks"
            :key="link.href"
            class="layout-navmenu-link"
            :href="link.href"
            >{{ link.label }}</Link
          >
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
        <summary class="btn btn-sm btn-outline-primary">Sign in</summary>
        <div class="layout-signin-menu">
          <a
            v-for="p in loginProviders"
            :key="p.id"
            class="layout-signin-link"
            :href="p.url"
            >{{ p.name }}</a
          >
        </div>
      </details>
      <a
        v-else
        class="btn btn-sm btn-outline-primary ms-auto"
        href="/accounts/login/"
      >
        Sign in
      </a>
    </HideOnScroll>
    <slot />
  </div>
</template>
