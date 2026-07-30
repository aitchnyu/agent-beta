<script setup lang="ts">
import { computed } from "vue"
import { router } from "@inertiajs/vue3"
import Layout from "../../components/Layout.vue"
import NoteForm from "../../components/ours/NoteForm.vue"
import { z } from "zod"

// Validate the server payload shape; parse() throws loudly if it drifts.
const NoteSchema = z.object({
  public_id: z.string(),
  title: z.string(),
  body: z.string(),
  owner_public_id: z.string(),
  owner_title: z.string(),
})

const props = defineProps<{ notes: unknown[] }>()
const notes = computed(() => NoteSchema.array().parse(props.notes))

function onCreated() {
  // The server is the source of truth — reload the list after a create.
  router.reload()
}
</script>

<template>
  <Layout>
    <div class="container ours-notes-page">
      <h1>Notes</h1>
      <NoteForm @created="onCreated" />
      <ul class="ours-notes-list">
        <li v-for="note in notes" :key="note.public_id">
          <strong>{{ note.title }}</strong> — {{ note.owner_title }}
          <p v-if="note.body">{{ note.body }}</p>
        </li>
      </ul>
    </div>
  </Layout>
</template>
