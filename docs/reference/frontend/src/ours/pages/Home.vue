<script setup lang="ts">
import { computed } from "vue"
// Framework layout sits at frontend/src/components/Layout.vue; from
// src/ours/pages/ that is two levels up to src/ then into components/.
import Layout from "../../components/Layout.vue"
import { getCsrfToken } from "../../utils/csrf"
import { HomePropsSchema } from "../schemas"
// Side-effect import: the app ships its own styles from ours/style.scss, so the
// feature is self-contained (no edit to the framework's main.scss).
import "../style.scss"

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
const props = defineProps<{ props: object }>()
const p = computed(() => HomePropsSchema.parse(props.props))
const csrfToken = computed(() => getCsrfToken())
</script>

<template>
  <Layout>
    <div class="home-container">
      <h1>Instant</h1>
      <p v-if="p.is_authenticated" class="home-status home-status-signed-in">
        Signed in as
        <strong class="home-display-name">{{ p.display_name }}</strong>
      </p>
      <p v-else class="home-status home-status-signed-out">
        You are not signed in.
      </p>

      <nav class="home-feature-nav">
        <a class="home-feature-link" href="/facts">Facts</a>
        <!-- Todos is auth-required (anon GET /todos is 404), so only signed-in
             viewers see its link — never link a viewer into a page they can't open. -->
        <a v-if="p.is_authenticated" class="home-feature-link" href="/todos">
          Todos
        </a>
      </nav>

      <!-- Signed out: a Google login link. -->
      <a
        v-if="!p.is_authenticated"
        class="home-login-link"
        href="/accounts/google/login/"
      >
        Sign in with Google
      </a>
      <!-- Signed in: a logout button (POSTs to allauth, redirects to LOGOUT_REDIRECT_URL). -->
      <form
        v-else
        action="/accounts/logout/"
        method="post"
        class="home-logout-form"
      >
        <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken" />
        <button class="home-logout-btn" type="submit">Sign out</button>
      </form>
    </div>
  </Layout>
</template>
