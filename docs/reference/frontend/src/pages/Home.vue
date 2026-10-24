<script setup lang="ts">
import { computed } from "vue"
import { Link, usePage } from "@inertiajs/vue3"
import { z } from "zod"
import { FactSchema } from "../schemas/facts"
import { SharedPropsSchema } from "../system/schemas/sharedProps"
// Side-effect import: the app ships its own styles from styles/app.scss, so the
// feature is self-contained (no edit to the framework's main.scss).
import "../styles/app.scss"

// The landing page's own props: the Fact of the Day (today's fixed pick,
// chosen by a Huey daily cron, or null). Login state is the shared viewer
// (`user`, injected on every page by SharedPropsMiddleware).
const HomePropsSchema = z.object({
  fact_of_day: FactSchema.nullable(),
})

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
const props = defineProps<{ props: object }>()
const p = computed(() => HomePropsSchema.parse(props.props))
const shared = computed(() => SharedPropsSchema.parse(usePage().props))
const isAuthenticated = computed(() => shared.value.user !== null)
// The superuser flag gates the Downloads manager link.
const isSuperuser = computed(() => shared.value.viewer_is_superuser)
</script>

<template>
    <div class="home-container">
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

      <!-- Auth chrome lives in the framework navbar (Layout's sign-in dropdown /
           user menu); the page itself only addresses anonymous visitors. -->
      <p v-if="!isAuthenticated" class="home-status home-status-signed-out">
        You are not signed in.
      </p>

      <nav class="home-feature-nav">
        <Link class="home-feature-link" href="/facts">Facts</Link>
        <!-- Todos is auth-required (anon GET /todos is 404), so only signed-in
             viewers see its link — never link a viewer into a page they can't open. -->
        <a v-if="isAuthenticated" class="home-feature-link" href="/todos">
          Todos
        </a>
        <!-- Downloads is the superuser-only upload manager (plain <a> like
             its siblings — the nav is not SPA-navigated). -->
        <a v-if="isSuperuser" class="home-feature-link" href="/downloads">
          Downloads
        </a>
      </nav>

      <!-- Signed out: a generic sign-in link — the provider buttons live on
           the allauth login page (rendered from the configured SocialApps). -->
      <a
        v-if="!isAuthenticated"
        class="home-login-link"
        href="/accounts/login/"
      >
        Sign in
      </a>
    </div>
</template>
