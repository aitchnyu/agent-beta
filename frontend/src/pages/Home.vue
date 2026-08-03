<script setup lang="ts">
import { computed } from "vue"
import Layout from "../components/Layout.vue"
import { getCsrfToken } from "../utils/csrf"
import { HomePropsSchema } from "../schemas"

const props = defineProps<{ props: object }>()

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
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
