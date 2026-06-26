<script setup lang="ts">
import { computed, type PropType } from "vue"
import { Link } from "@inertiajs/vue3"
import { getCsrfToken } from "../utils/csrf"

interface NavBarUser {
  public_id: string
  title: string
}

const props = defineProps({
  user: {
    type: Object as PropType<NavBarUser | null>,
    default: null,
  },
  isSuperuser: {
    type: Boolean,
    default: false,
  },
})

const csrfToken = computed(() => getCsrfToken())
</script>

<template>
  <div class="layout-navbar">
    <Link
      v-if="props.isSuperuser"
      class="btn btn-outline-secondary btn-sm"
      href="/users/list"
    >
      Users
    </Link>
    <template v-if="props.user">
      <span class="layout-user">
        Hello,
        <Link :href="`/users/id/${props.user.public_id}`">{{
          props.user.title
        }}</Link
        >!
      </span>
      <form action="/accounts/logout/" method="post" class="layout-logout-form">
        <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken" />
        <button class="btn btn-sm btn-outline-primary" type="submit">
          Logout
        </button>
      </form>
    </template>
    <a
      v-else
      class="btn btn-sm btn-outline-primary"
      href="/accounts/google/login/"
    >
      Login with Google
    </a>
    <slot />
  </div>
</template>
