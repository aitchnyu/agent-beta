<script setup lang="ts">
import { computed } from "vue"
import { Link } from "@inertiajs/vue3"
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
    <div class="home-container">
      <h1>Instant</h1>

      <!-- Today's Fact of the Day: one fixed pick per local date (Huey cron). -->
      <section v-if="p.fact_of_day" class="home-fact-of-day">
        <h2>Fact of the Day</h2>
        <p>
          <Link class="ours-fact-text" :href="`/fact/${p.fact_of_day.public_id}`">{{
            p.fact_of_day.text
          }}</Link>
        </p>
        <p class="text-muted">
          Topic:
          <Link :href="`/facts/${p.fact_of_day.topic.slug}`">{{
            p.fact_of_day.topic.name
          }}</Link>
        </p>
      </section>
      <p v-else class="text-muted">
        No facts yet — run <code>./run djangomanage seedfacts</code>.
      </p>

      <p v-if="p.is_authenticated" class="home-status home-status-signed-in">
        Signed in as
        <strong class="home-display-name">{{ p.display_name }}</strong>
      </p>
      <p v-else class="home-status home-status-signed-out">
        You are not signed in.
      </p>

      <nav class="home-feature-nav">
        <Link class="home-feature-link" href="/facts">Facts</Link>
        <!-- Todos is auth-required (anon GET /todos is 404), so only signed-in
             viewers see its link — never link a viewer into a page they can't open. -->
        <a v-if="p.is_authenticated" class="home-feature-link" href="/todos">
          Todos
        </a>
      </nav>

      <!-- Signed out: a generic sign-in link — the provider buttons live on
           the allauth login page (rendered from the configured SocialApps). -->
      <a
        v-if="!p.is_authenticated"
        class="home-login-link"
        href="/accounts/login/"
      >
        Sign in
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
</template>
