<script setup lang="ts">
import { computed } from "vue"
import { Link, router } from "@inertiajs/vue3"
// Framework layout sits at frontend/src/components/Layout.vue; from
// src/ours/pages/ that is two levels up to src/ then into components/.
import Layout from "../../components/Layout.vue"
import NoteForm from "../components/NoteForm.vue"
import { noteSummary } from "../utils/format"
import { NotesPagePropsSchema } from "../schemas"
// Side-effect import: the app ships its own styles from ours/style.scss, so the
// feature is self-contained (no edit to the framework's main.scss).
import "../style.scss"

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
const props = defineProps<{ props: object }>()
const notes = computed(() => NotesPagePropsSchema.parse(props.props).notes)

function onCreated() {
  // The server is the source of truth — reload the list after a create.
  router.reload()
}
</script>

<template>
  <Layout>
    <div class="ours-notes-page">
      <h1>Notes</h1>
      <NoteForm @created="onCreated" />
      <ul class="ours-notes-list">
        <li v-for="note in notes" :key="note.public_id">
          <Link :href="`/notes/${note.public_id}`"><strong>{{ note.title }}</strong></Link>
          — {{ note.owner_title }}
          <p v-if="note.body">{{ noteSummary(note.body) }}</p>
        </li>
      </ul>
    </div>
  </Layout>
</template>
