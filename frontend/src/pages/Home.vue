<script setup lang="ts">
import { computed } from "vue"
import { HomePropsSchema } from "../schemas"
import { getCsrfToken } from "../utils/csrf"

const props = defineProps<{
  is_authenticated: boolean
  display_name: string
  public_id: string
}>()

// Validate the server payload shape; parse() throws loudly if it drifts.
const p = computed(() => HomePropsSchema.parse(props))

const csrfToken = computed(() => getCsrfToken())
</script>

<template>
  <div class="home-container">
    <h1>Instant</h1>
    <p v-if="p.is_authenticated" class="home-status home-status-signed-in">
      Signed in as
      <strong class="home-display-name">{{ p.display_name }}</strong>
    </p>
    <p v-else class="home-status home-status-signed-out">
      You are not signed in.
    </p>

    <a
      v-if="!p.is_authenticated"
      class="login-link home-login-link"
      href="/accounts/google/login/"
      >Sign in with Google</a
    >
    <form
      v-else
      class="home-logout-form"
      action="/accounts/logout/"
      method="post"
    >
      <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken" />
      <button class="logout-btn home-logout-btn" type="submit">Sign out</button>
    </form>
  </div>
</template>
