<template>
  <Layout>
    <p>Seeded rows: <span class="ref-count">{{ count }}</span></p>
    <button class="btn btn-primary btn-sm ref-refresh" :disabled="loading" @click="refresh">
      Refresh
    </button>
    <p v-if="fetched !== null" class="ref-fetched">{{ fetched }}</p>
  </Layout>
</template>

<script setup lang="ts">
import { ref } from "vue"
import axios from "axios"
import { z } from "zod"
import Layout from "../components/Layout.vue"
import { showErrorToast } from "../utils/showErrorToast"

// Host convention: page props are nested under a "props" key.
const { props } = defineProps<{ props: { count: number } }>()
const count = ref(props.count)
const fetched = ref<number | null>(null)
const loading = ref(false)

// Validate the endpoint response; never swallow errors silently.
const CountOut = z.object({ count: z.number() })

async function refresh() {
  loading.value = true
  try {
    const res = await axios.get("/apps/a/Reference/Demo/endpoint/get/current_count")
    fetched.value = CountOut.parse(res.data).count
  } catch (e) {
    showErrorToast(e, "Could not load the count")
  } finally {
    loading.value = false
  }
}
</script>
