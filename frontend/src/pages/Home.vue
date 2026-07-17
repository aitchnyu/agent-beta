<script setup lang="ts">
import { computed } from "vue"
import Layout from "../components/Layout.vue"
import { HomePropsSchema } from "../schemas"

const props = defineProps<{
  is_authenticated: boolean
  display_name: string
  public_id: string
}>()

// Validate the server payload shape; parse() throws loudly if it drifts.
const p = computed(() => HomePropsSchema.parse(props))
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
    </div>
  </Layout>
</template>
