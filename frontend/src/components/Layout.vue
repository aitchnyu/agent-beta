<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import { Link, usePage } from "@inertiajs/vue3"
import { getCsrfToken } from "../utils/csrf"
import { SharedPropsSchema } from "../schemas"
import NotificationsBell from "./NotificationsBell.vue"

// The signed-in viewer's profile + superuser flag are Inertia shared props,
// injected for every page by SharedPropsMiddleware (not threaded per-view).
const page = usePage()
const shared = computed(() => SharedPropsSchema.parse(page.props))
const user = computed(() => shared.value.user)
const isSuperuser = computed(() => shared.value.viewer_is_superuser)
const loginProviders = computed(() => shared.value.login_providers)

const csrfToken = computed(() => getCsrfToken())

// Native <details> dropdown for Sign in: closes on any outside click
// (it would otherwise stay open; links inside navigate away, closing it).
const signin = ref<HTMLDetailsElement>()
function onDocClick(e: MouseEvent) {
  const el = signin.value
  if (el?.open && !el.contains(e.target as Node)) el.open = false
}
onMounted(() => document.addEventListener("click", onDocClick))
onBeforeUnmount(() => document.removeEventListener("click", onDocClick))
</script>

<template>
  <div>
    <div class="layout-navbar">
      <Link v-if="isSuperuser" class="nav-link" href="/manage/models">
        Models
      </Link>
      <Link v-if="isSuperuser" class="nav-link" href="/git/uncommitted/">
        Code
      </Link>
      <Link v-if="isSuperuser" class="nav-link" href="/users/list">
        Users
      </Link>
      <template v-if="user">
        <span class="layout-user ms-auto">
          Hello,
          <Link :href="`/users/id/${user.public_id}`">{{ user.title }}</Link
          >!
        </span>
        <NotificationsBell />
        <form
          action="/accounts/logout/"
          method="post"
          class="layout-logout-form"
        >
          <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken" />
          <button class="btn btn-sm btn-outline-primary" type="submit">
            Logout
          </button>
        </form>
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
    </div>
    <slot />
  </div>
</template>
