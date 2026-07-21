<template>
  <div>
    <!-- The seeded value, rendered from the Inertia prop. -->
    <p class="browser-value">{{ value }}</p>
    <!-- Fires the app's GET endpoint and shows the result (interaction). -->
    <button class="browser-refresh" :disabled="loading" @click="refresh">Refresh</button>
    <p v-if="fetched" class="browser-fetched">{{ fetched }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import axios from "axios"

// Host convention: page props are nested under a "props" key.
const { props } = defineProps<{ props: { value: string } }>()
const value = props.value

const fetched = ref<string>("")
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    const res = await axios.get("/apps/BrowserApp/e/current_value")
    fetched.value = res.data.value
  } catch {
    fetched.value = "error"
  } finally {
    loading.value = false
  }
}
</script>
