<script setup lang="ts">
import { computed } from "vue"
import { Link } from "@inertiajs/vue3"
import Layout from "../../components/Layout.vue"
import { NoteDetailPagePropsSchema } from "../schemas"
import "../style.scss"

// Inertia wraps the page data under a `props` key (page.props.props); parse it.
const props = defineProps<{ props: object }>()
const p = computed(() => NoteDetailPagePropsSchema.parse(props.props))
</script>

<template>
  <Layout>
    <div class="ours-note-detail">
      <h1>{{ p.note.title }}</h1>
      <p class="text-muted">
        Owner: {{ p.note.owner_title }} · Revisions: {{ p.revisions }}
      </p>
      <p v-if="p.note.body" class="ours-note-body">{{ p.note.body }}</p>
      <p v-else class="text-muted">(no body)</p>
      <p>
        <Link class="btn btn-secondary btn-sm me-2" :href="`/notes/${p.note.public_id}/edit`">Edit</Link>
        <Link class="text-muted" href="/notes">Back to notes</Link>
      </p>
    </div>
  </Layout>
</template>
