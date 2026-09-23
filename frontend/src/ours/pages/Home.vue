<script setup lang="ts">
import { computed } from "vue"
// Framework layout sits at frontend/src/components/Layout.vue; from
// src/ours/pages/ that is two levels up to src/ then into components/.
import PageTitle from "../../components/PageTitle.vue"
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
    <h1>Instant</h1>
    <p class="home-placeholder-note text-muted">
      This is a placeholder app, not a finished product — add your features
      under <code>ourapp/</code> and <code>frontend/src/ours/</code> (see
      <code>docs/reference/</code> for a complete example).
    </p>
    <p v-if="!p.is_authenticated" class="home-status home-status-signed-out">
      You are not signed in.
    </p>
  </div>
</template>
