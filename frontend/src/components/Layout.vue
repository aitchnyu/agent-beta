<script setup lang="ts">
import { computed } from "vue"
import { Link, usePage } from "@inertiajs/vue3"
import { getCsrfToken } from "../utils/csrf"
import { SharedPropsSchema } from "../schemas"

// The signed-in viewer's profile + superuser flag are Inertia shared props,
// injected for every page by SharedPropsMiddleware (not threaded per-view).
const page = usePage()
const shared = computed(() => SharedPropsSchema.parse(page.props))
const user = computed(() => shared.value.user)
const isSuperuser = computed(() => shared.value.viewer_is_superuser)

const csrfToken = computed(() => getCsrfToken())
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
