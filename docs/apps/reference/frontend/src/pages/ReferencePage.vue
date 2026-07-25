<template>
  <Layout>
    <p>Rows: <span class="ref-count">{{ count }}</span></p>
    <button class="btn btn-primary btn-sm ref-refresh" :disabled="loading" @click="refresh">
      Refresh
    </button>
    <p v-if="fetched !== null" class="ref-fetched">{{ fetched }}</p>

    <form class="row g-2 mt-3 align-items-center" @submit.prevent="addItem">
      <div class="col-auto">
        <input
          v-model="newCode"
          class="form-control form-control-sm ref-new-code"
          maxlength="10"
          placeholder="code (≤ 10)"
        />
      </div>
      <div class="col-auto">
        <button class="btn btn-success btn-sm ref-add" :disabled="adding" type="submit">Add</button>
      </div>
    </form>
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
const newCode = ref("")
const adding = ref(false)

// Named endpoints share the /apps/<app>/e prefix; hoist it so renames touch one place.
const ENDPOINTS = "/apps/ReferenceDemo/e"

// Validate endpoint responses; never swallow errors silently.
const CountOut = z.object({ count: z.number() })
const ItemOut = z.object({ code: z.string() })

async function refresh() {
  loading.value = true
  try {
    const res = await axios.get(`${ENDPOINTS}/current_count`)
    fetched.value = CountOut.parse(res.data).count
  } catch (e) {
    showErrorToast(e, "Could not load the count")
  } finally {
    loading.value = false
  }
}

async function addItem() {
  const code = newCode.value.trim()
  if (!code) return
  adding.value = true
  try {
    const res = await axios.post(`${ENDPOINTS}/add_item`, { code })
    ItemOut.parse(res.data) // validate the created item
    newCode.value = ""
    await refresh() // re-fetch the count so the new row is reflected
  } catch (e) {
    showErrorToast(e, "Could not add the item")
  } finally {
    adding.value = false
  }
}
</script>
