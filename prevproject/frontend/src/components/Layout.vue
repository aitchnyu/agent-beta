<script setup lang="ts">
import { computed, type PropType } from "vue"
import { Link, usePage } from "@inertiajs/vue3"

defineProps({
  user: {
    type: Object as PropType<{ title: string } | null>,
    default: null,
  },
})

const page = usePage()
const notificationCount = computed(
  () => (page.props.notification_count as number) || 0,
)
</script>

<template>
  <div style="margin: 0; padding: 0.5rem 1rem">
    <Link class="btn btn-outline-secondary btn-sm" href="/tables/_debug">
      Debug Page
    </Link>
    <Link
      class="btn btn-outline-secondary btn-sm"
      href="/tables/notifications/page"
    >
      Notifications
      <span v-if="notificationCount > 0" class="notification-badge">{{
        notificationCount
      }}</span>
    </Link>
    <template v-if="user">
      <span class="mb-3">Hello, {{ user.title }}!</span>
      <a class="btn btn-sm btn-outline-primary" href="/accounts/logout"
        >Logout</a
      >
    </template>
    <a
      v-else
      class="btn btn-sm btn-outline-primary"
      href="/accounts/google/login/?next=/tables/_debug"
      >Login with Google</a
    >
    <slot />
  </div>
</template>
