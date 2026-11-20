<script setup lang="ts">
import { computed } from "vue"
import PageTitle from "../../system/components/PageTitle.vue"
import { useSharedProps } from "../../system/utils/useAppPage"
// Side-effect import: the app ships its own styles from styles/app.scss, so
// the app is self-contained (no edit to the system stylesheet).
import "../styles/app.scss"

// Login state is the shared viewer `user`, injected on every page by
// SharedPropsMiddleware.
const shared = useSharedProps()
const isAuthenticated = computed(() => shared.value.user !== null)
</script>

<template>
  <PageTitle />
  <div class="home-container">
    <p class="home-placeholder-note text-muted">
      Agent instruction: this page is throwaway placeholder scaffolding — remove
      ALL of it (both the logged-in and the anonymous signed-out content) as
      soon as possible, in mockup time itself.
    </p>
    <template v-if="isAuthenticated">
      <p class="home-placeholder-note text-muted">
        This is a placeholder app, not a finished product — add your features:
      </p>
      <p class="home-placeholder-note text-muted">
        Prompt pi to build your first feature — one message is enough:
      </p>
      <img
        class="home-shot"
        :src="'/static/pi/prompt-tracker.png'"
        alt="prompting pi: I want to create a tracker for watering the plants — any logged in user can mark each day as done or not done"
      />
    </template>
    <template v-else>
      <div
        class="home-status-signed-out alert alert-warning d-flex flex-column gap-2"
      >
        <p class="mb-0">
          You are not logged in — mockups, design docs, and the admin surfaces
          are visible to superusers only.
        </p>
        <p class="mb-0">
          Ask your agent to set one up:
          <code class="d-block"
            >create a new superuser John Smith with john.smith@example.com and
            send a login link</code
          >
        </p>
      </div>
      <p class="home-placeholder-note text-muted">
        What prompting looks like — the first message carries the admin setup
        and the feature together:
      </p>
      <img
        class="home-shot"
        :src="'/static/pi/prompt-superuser-tracker.png'"
        alt="prompting pi: create a new superuser John Smith with john@example.com, send a login link, and request a plant-watering tracker in one message"
      />
    </template>
  </div>
</template>
