<template>
  <div>
    <!-- The seeded row's code, rendered from the Inertia prop. -->
    <p class="demo-label">{{ label }}</p>
    <!-- Fires the app's GET endpoint and shows the result (interaction). -->
    <button class="demo-refresh" :disabled="loading" @click="refresh">Refresh</button>
    <p v-if="fetched" class="demo-fetched">{{ fetched }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import axios from "axios"

// Host convention: page props are nested under a "props" key.
const { props } = defineProps<{ props: { label: string } }>()
const label = props.label

const fetched = ref<string>("")
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    const res = await axios.get("/apps/a/Tests/Page/endpoint/get/current_code")
    fetched.value = res.data.code
  } catch {
    fetched.value = "error"
  } finally {
    loading.value = false
  }
}
</script>
