<script setup lang="ts">
import { computed } from "vue"
import { Link } from "@inertiajs/vue3"
// Framework layout sits at frontend/src/components/Layout.vue; from
// src/ours/pages/ that is two levels up to src/ then into components/.
import PageTitle from "../../components/PageTitle.vue"
import { fileUrl } from "../../utils/files"
import { HomePropsSchema } from "../schemas"
// Side-effect import: the app ships its own styles from ours/style.scss, so the
// feature is self-contained (no edit to the framework's main.scss).
import "../style.scss"

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
const props = defineProps<{ props: object }>()
const p = computed(() => HomePropsSchema.parse(props.props))
</script>

<template>
  <PageTitle />
  <div class="home-container">
    <template v-if="p.is_authenticated">
      <p class="home-placeholder-note text-muted">
        This is a placeholder app, not a finished product — add your features:
      </p>
      <ul class="home-points">
        <li>
          <Link :href="fileUrl('main/ourapp')"><code>ourapp/</code></Link> — the
          backend: one module per feature under models/, views/ and tests/
          (Django models, Ninja endpoints, Huey tasks).
        </li>
        <li>
          <Link :href="fileUrl('main/frontend/src/ours')"
            ><code>frontend/src/ours/</code></Link
          >
          — the frontend: one Vue page per feature under pages/, plus the shared
          props schemas and styles.
        </li>
        <li>
          <Link :href="fileUrl('main/docs/reference')"
            ><code>docs/reference/</code></Link
          >
          — a complete worked example of both — copy a feature from there and
          adapt it.
        </li>
      </ul>
    </template>
    <div v-else class="home-status home-status-signed-out">
      <p>You are not logged in. You may ask your agent:</p>
      <ul class="home-points">
        <li>Create a new superuser John Smith and send me a login link</li>
        <li>Create a login link for John Smith</li>
      </ul>
    </div>
  </div>
</template>
