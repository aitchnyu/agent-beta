<script setup lang="ts">
import axios from "axios"
import { ref } from "vue"
import { showErrorToast } from "../../utils/sweetalert"

// Emits `created` so the parent can reload the list (server is source of truth).
const emit = defineEmits<{ created: [] }>()

const title = ref("")
const body = ref("")

async function submit() {
  try {
    await axios.post("/notes/create", { title: title.value, body: body.value })
    title.value = ""
    body.value = ""
    emit("created")
  } catch (e) {
    showErrorToast(e, "Could not create note")
  }
}
</script>

<template>
  <form class="ours-note-form mb-4" @submit.prevent="submit">
    <input v-model="title" class="form-control mb-2" placeholder="Title" required />
    <textarea v-model="body" class="form-control mb-2" placeholder="Body" />
    <button class="btn btn-primary btn-sm" type="submit">Add note</button>
  </form>
</template>
